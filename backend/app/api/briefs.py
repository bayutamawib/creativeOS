import hashlib
import os
import tempfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy import select

from app.api.deps import Database, Identity
from app.brief_inputs import BriefEdit, BriefFields, Category, Paragraph, Version, Visibility
from app.brief_models import Brief, FileAsset, Snapshot
from app.config import settings
from app.models import Client, Project
from app.project_inputs import Portal
from app.schemas import Input
from app.services import agency, assets, briefs, projects

router = APIRouter()


@router.post("/files/upload", status_code=201)
async def upload(
    project_id: UUID,
    file_name: str,
    request: Request,
    db: Database,
    identity: Identity,
    portal: Portal | None = None,
    category: Category = "brief_attachment",
    visibility: Visibility | None = None,
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    projects.access(db, identity.user_id, project_id, mode)
    label = visibility or ("client_visible" if mode == "client" else "internal")
    if mode == "client" and label != "client_visible":
        raise HTTPException(403, "Internal files require agency access")
    mime = request.headers.get("content-type", "").split(";")[0].lower()
    if mime == "video/mp4":
        if settings().file_provider != "local":
            raise HTTPException(503, "Video requires local storage")
        assets.validate_name(file_name, mime)
        root = Path(settings().storage_dir)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, path = tempfile.mkstemp(prefix=".incoming-", dir=root)
        incoming = Path(path)
        size = 0
        digest = hashlib.sha256()
        try:
            with os.fdopen(descriptor, "wb") as target:
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > settings().video_max_bytes:
                        raise HTTPException(413, "Video exceeds the configured size limit")
                    digest.update(chunk)
                    target.write(chunk)
            p = briefs.context(db, identity.user_id, project_id, mode, write=True)
            row = assets.store_video_file(db, identity.user_id, p, file_name, incoming, size, digest.hexdigest(), category, label)
            return {"data": assets.metadata(row)}
        finally:
            incoming.unlink(missing_ok=True)
    body = bytearray()
    async for chunk in request.stream():
        if len(chunk) + len(body) > assets.MAX_BYTES:
            raise HTTPException(413, "Maximum upload size is 5 MiB")
        body.extend(chunk)
    p = briefs.context(db, identity.user_id, project_id, mode, write=True)
    row = assets.store(db, identity.user_id, p, file_name, mime, bytes(body), category, label)
    return {"data": assets.metadata(row)}


class CoverInput(Input):
    cover_file_id: UUID


@router.put("/files/{file_id}/cover")
def video_cover(file_id: UUID, data: CoverInput, db: Database, identity: Identity, portal: Portal | None = None) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": assets.metadata(assets.set_video_cover(db, identity.user_id, file_id, data.cover_file_id, mode))}


@router.api_route("/files/{file_id}/stream", methods=["GET", "HEAD"])
def video_stream(file_id: UUID, request: Request, db: Database, identity: Identity, portal: Portal | None = None) -> Response:
    mode = projects.effective_portal(db, identity.user_id, portal)
    row = assets.get(db, identity.user_id, file_id, mode)
    if row.mime_type != "video/mp4":
        raise HTTPException(415, "Video stream requires MP4")
    # Verify through bounded reads before returning any requested segment.
    source = assets.open_video(row)
    size = row.file_size
    start, end = 0, size - 1
    requested = request.headers.get("range")
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Vary": "Cookie",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    if requested:
        try:
            unit, value = requested.split("=", 1)
            if unit != "bytes" or "," in value or value.count("-") != 1:
                raise ValueError
            first, last = value.split("-", 1)
            if not first and not last:
                raise ValueError
            if first:
                start = int(first)
                end = min(int(last), size - 1) if last else size - 1
            else:
                count = int(last)
                if count <= 0:
                    raise ValueError
                start = max(0, size - count)
            if start < 0 or start >= size or end < start:
                raise ValueError
        except ValueError:
            source.close()
            return Response(status_code=416, headers=headers | {"Content-Range": f"bytes */{size}"})
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1)
    if request.method == "HEAD":
        source.close()
        return Response(status_code=206 if requested else 200, media_type="video/mp4", headers=headers)

    def chunks() -> Iterator[bytes]:
        with source:
            source.seek(start)
            remaining = end - start + 1
            while remaining:
                block = source.read(min(64 * 1024, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block

    return StreamingResponse(chunks(), status_code=206 if requested else 200, media_type="video/mp4", headers=headers)


@router.get("/files")
def files(
    db: Database,
    identity: Identity,
    project_id: UUID | None = None,
    portal: Portal | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    rows = db.execute(
        assets.visible(db, identity.user_id, mode, project_id)
        .add_columns(Project.name)
        .join(Project, Project.id == FileAsset.project_id)
        .order_by(FileAsset.created_at.desc(), FileAsset.id)
        .offset((page - 1) * 50)
        .limit(50)
    )
    return {"data": [assets.metadata(row) | {"project_name": name} for row, name in rows]}


@router.get("/files/{file_id}")
def file(
    file_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": assets.metadata(assets.get(db, identity.user_id, file_id, mode))}


@router.get("/files/{file_id}/download")
def download(
    file_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> Response:
    mode = projects.effective_portal(db, identity.user_id, portal)
    row = assets.get(db, identity.user_id, file_id, mode)
    if row.mime_type == "video/mp4":
        source = assets.open_video(row)

        def chunks() -> Iterator[bytes]:
            with source:
                yield from iter(lambda: source.read(64 * 1024), b"")

        return StreamingResponse(
            chunks(), media_type="video/mp4",
            headers={
                "Content-Length": str(row.file_size),
                "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.file_name, safe=""),
                "Cache-Control": "private, no-store",
                "Vary": "Cookie",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox",
            },
        )
    return Response(
        assets.download(row),
        media_type=row.mime_type,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''" + quote(row.file_name, safe=""),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.get("/files/{file_id}/preview")
@router.get("/files/{file_id}/thumbnail")
def image_media(
    file_id: UUID,
    request: Request,
    db: Database,
    identity: Identity,
    portal: Portal | None = None,
) -> Response:
    mode = projects.effective_portal(db, identity.user_id, portal)
    row = assets.get(db, identity.user_id, file_id, mode)
    if row.mime_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(415, "Image preview requires a PNG or JPEG")
    body = assets.download(row)
    if request.url.path.endswith("/thumbnail"):
        with Image.open(BytesIO(body)) as source:
            source.thumbnail((640, 480))
            output = BytesIO()
            source.save(output, format="PNG")
            body = output.getvalue()
        mime = "image/png"
    else:
        mime = row.mime_type
    return Response(
        body,
        media_type=mime,
        headers={
            "Cache-Control": "private, no-store",
            "Vary": "Cookie",
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/files/{file_id}", status_code=204)
def archive(file_id: UUID, db: Database, identity: Identity) -> None:
    assets.archive(db, identity.user_id, file_id)


@router.get("/briefs")
@router.get("/projects/{project_id}/briefs")
def listing(
    db: Database,
    identity: Identity,
    project_id: UUID | None = None,
    portal: Portal | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    stmt = select(Brief).where(
        Brief.project_id.in_(
            projects.scope(db, identity.user_id, mode).with_only_columns(Project.id)
        )
    )
    if project_id:
        projects.access(db, identity.user_id, project_id, mode)
        stmt = stmt.where(Brief.project_id == project_id)
    rows = db.scalars(
        stmt.order_by(Brief.updated_at.desc(), Brief.id).offset((page - 1) * 50).limit(50)
    )
    return {"data": briefs.views(db, rows.all())}


@router.post("/projects/{project_id}/briefs", status_code=201)
def create(
    project_id: UUID,
    data: BriefFields,
    db: Database,
    identity: Identity,
    portal: Portal | None = None,
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": briefs.view(db, briefs.create(db, identity.user_id, project_id, mode, data))}


@router.get("/briefs/{brief_id}")
def detail(
    brief_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": briefs.view(db, briefs.get(db, identity.user_id, brief_id, mode))}


@router.patch("/briefs/{brief_id}")
def edit(
    brief_id: UUID, data: BriefEdit, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": briefs.view(db, briefs.edit(db, identity.user_id, brief_id, mode, data))}


def add_transition(action: str) -> None:
    def apply(brief_id: UUID, data: Version, db: Database, identity: Identity) -> dict[str, Any]:
        return {
            "data": briefs.view(db, briefs.transition(db, identity.user_id, brief_id, action, data))
        }

    router.add_api_route(
        "/briefs/{brief_id}/" + action, apply, methods=["POST"], name="brief_" + action
    )


for command in ("submit", "start-review", "request-revision", "approve", "reject"):
    add_transition(command)


class BrandInput(Input):
    guidance: Paragraph


@router.put("/clients/{client_id}/brand-guidelines")
def brand(client_id: UUID, data: BrandInput, db: Database, identity: Identity) -> dict[str, Any]:
    agency.guard_operational_write(db)
    agency.manager_roles(db, identity.user_id)
    row = db.get(Client, client_id, with_for_update=True)
    if not row:
        raise HTTPException(404, "Client not found")
    row.brand_guidelines = data.model_dump()
    agency.audit(db, identity.user_id, "client.brand_guidelines", client_id, {})
    return {"data": row.brand_guidelines}


@router.get("/briefs/{brief_id}/snapshots")
def approval_history(
    brief_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    briefs.get(db, identity.user_id, brief_id, mode)
    snapshots = db.scalars(
        select(Snapshot).where(Snapshot.brief_id == brief_id).order_by(Snapshot.version.desc())
    )
    return {
        "data": [
            {
                "id": s.id,
                "version": s.version,
                "approved_at": s.created_at,
                "fields": s.fields,
                "attachments": s.attachments,
            }
            for s in snapshots
        ]
    }
