"""Private Drive files owned by the configured OAuth account."""

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.config import settings


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


class DriveStorage:
    def _call(self, path: str, method: str, data: bytes | None = None, mime: str = "") -> bytes:
        secret = settings().drive_access_token
        if not secret or not secret.get_secret_value():
            raise HTTPException(503, "Drive credentials unavailable")
        headers = {"Authorization": "Bearer " + secret.get_secret_value()}
        if mime:
            headers["Content-Type"] = mime
        req = Request(
            "https://www.googleapis.com/" + path, method=method, data=data, headers=headers
        )
        try:
            with build_opener(_NoRedirect()).open(req, timeout=15) as response:
                body: bytes = response.read(5 * 1024 * 1024 + 1)
                if len(body) > 5 * 1024 * 1024:
                    raise HTTPException(503, "Stored file exceeds limit")
                return body
        except (HTTPError, URLError, OSError) as exc:
            raise HTTPException(503, "Drive storage unavailable") from exc

    def put(self, key: UUID, body: bytes, mime: str) -> str:
        boundary = uuid4().hex
        metadata = json.dumps({"name": key.hex, "mimeType": mime}).encode()
        data = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
            + metadata
            + f"\r\n--{boundary}\r\nContent-Type: {mime}\r\n\r\n".encode()
            + body
            + f"\r\n--{boundary}--\r\n".encode()
        )
        reply = self._call(
            "upload/drive/v3/files?uploadType=multipart&fields=id",
            "POST",
            data,
            "multipart/related; boundary=" + boundary,
        )
        try:
            ref = json.loads(reply)["id"]
            if not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", ref):
                raise ValueError
            return ref
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(503, "Invalid Drive storage reference") from exc

    def path(self, ref: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", ref):
            raise HTTPException(503, "Invalid storage reference")
        return "drive/v3/files/" + ref

    def read(self, ref: str) -> bytes:
        return self._call(self.path(ref) + "?alt=media", "GET")

    def discard(self, ref: str) -> None:
        self._call(self.path(ref), "DELETE")
