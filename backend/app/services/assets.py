import hashlib
import os
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID, uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy import Select, event, select
from sqlalchemy.orm import Session

from app.brief_inputs import Category, Visibility
from app.brief_models import BriefFile, FileAsset, SnapshotFile
from app.config import settings
from app.models import Project
from app.project_inputs import Portal
from app.security import now
from app.services import agency, projects
from app.services.drive import DriveStorage

MAX_BYTES = 5 * 1024 * 1024
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".txt": "text/plain"}


class Storage(Protocol):
    def put(self, key: UUID, body: bytes, mime: str) -> str: ...
    def read(self, key: str) -> bytes: ...
    def discard(self, key: str) -> None: ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, key: UUID, body: bytes, mime: str) -> str:
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self.root / key.hex
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as stream:
            try:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            except OSError:
                path.unlink(missing_ok=True)
                raise

        return key.hex

    def read(self, key: str) -> bytes:
        try:
            return (self.root / UUID(key).hex).read_bytes()
        except FileNotFoundError as err:
            raise HTTPException(503, "File storage unavailable") from err

    def discard(self, key: str) -> None:
        (self.root / UUID(key).hex).unlink(missing_ok=True)


def storage(provider: str) -> Storage:
    if provider == "google_drive":
        return DriveStorage()
    if provider == "local":
        return LocalStorage(Path(settings().storage_dir))
    raise HTTPException(503, "Unknown storage provider")


def validate(name: str, mime: str, body: bytes) -> bytes:
    if (
        not name
        or len(name) > 180
        or name.startswith(".")
        or name != name.strip()
        or any(c in "/\\:" or unicodedata.category(c).startswith("C") for c in name)
    ):
        raise HTTPException(422, "Invalid filename")
    if not body or len(body) > MAX_BYTES:
        raise HTTPException(413, "File must be between 1 byte and 5 MiB")
    if TYPES.get(Path(name).suffix.lower()) != mime:
        raise HTTPException(415, "Choose a PNG, JPEG or plain text file with a matching media type")
    if mime == "text/plain":
        try:
            value = body.decode("utf-8")
        except UnicodeDecodeError as err:
            raise HTTPException(415, "Expected UTF-8 text") from err
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise HTTPException(415, "Invalid text file")
        return body
    try:
        with Image.open(BytesIO(body), formats=["JPEG", "PNG"]) as im:
            fmt = im.format
            if (
                Image.MIME.get(fmt or "") != mime
                or im.width * im.height > 8_000_000
                or getattr(im, "n_frames", 1) != 1
            ):
                raise ValueError
            im.load()
            result = BytesIO()
            # Re-encode decoded pixels to discard metadata and trailing payloads.
            clean = im.convert("RGBA" if fmt == "PNG" else "RGB")
            clean.info.clear()
            clean.save(result, format=fmt)
            if result.tell() > MAX_BYTES:
                raise HTTPException(413, "Decoded file exceeds storage limit")
            return result.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        SyntaxError,
    ) as err:
        raise HTTPException(415, "Invalid or oversized image") from err


def store(
    db: Session,
    actor: UUID,
    p: Project,
    name: str,
    mime: str,
    data: bytes,
    category: Category,
    visibility: Visibility,
) -> FileAsset:
    body = validate(name, mime, data)
    key = uuid4()
    asset = FileAsset(
        id=key,
        project_id=p.id,
        client_id=p.client_id,
        uploaded_by=actor,
        provider=settings().file_provider,
        file_name=name,
        mime_type=mime,
        file_size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        category=category,
        visibility=visibility,
    )
    db.add(asset)
    db.flush()
    adapter = storage(asset.provider)
    ref = adapter.put(key, body, mime)
    asset.provider_ref = ref
    event.listen(db, "after_rollback", lambda _: adapter.discard(ref), once=True)
    projects.change_log(db, actor, p, "file.uploaded", key)
    return asset


def visible(
    db: Session, actor: UUID, portal: Portal, project_id: UUID | None = None
) -> Select[FileAsset]:
    stmt = select(FileAsset).where(
        FileAsset.project_id.in_(projects.scope(db, actor, portal).with_only_columns(Project.id)),
        FileAsset.archived_at.is_(None),
    )
    if project_id:
        projects.access(db, actor, project_id, portal)
        stmt = stmt.where(FileAsset.project_id == project_id)
    if portal == "client":
        stmt = stmt.where(FileAsset.visibility == "client_visible")
    return stmt


def get(db: Session, actor: UUID, key: UUID, portal: Portal) -> FileAsset:
    row = db.scalar(visible(db, actor, portal).where(FileAsset.id == key))
    if not row:
        raise HTTPException(404, "File not found")
    return row


def metadata(row: FileAsset) -> dict[str, Any]:
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "project_id",
            "file_name",
            "mime_type",
            "file_size",
            "category",
            "visibility",
            "created_at",
            "provider",
        )
    }


def archive(db: Session, actor: UUID, key: UUID) -> None:
    row = get(db, actor, key, "agency")
    agency.guard_operational_write(db)
    p = projects.access(db, actor, row.project_id, "agency", write=True)
    if db.scalar(select(BriefFile.id).where(BriefFile.file_id == key).limit(1)) or db.scalar(
        select(SnapshotFile.id).where(SnapshotFile.file_id == key).limit(1)
    ):
        raise HTTPException(409, "Referenced files must be retained")
    row.archived_at = now()
    projects.change_log(db, actor, p, "file.archived", key)


def download(row: FileAsset) -> bytes:
    body = storage(row.provider).read(row.provider_ref or row.id.hex)
    if hashlib.sha256(body).hexdigest() != row.sha256:
        raise HTTPException(503, "Stored file integrity check failed")
    return body
