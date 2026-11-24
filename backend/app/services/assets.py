import hashlib
import os
import stat
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Protocol
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
from app.review_models import Review, RevisionFile
from app.security import now
from app.services import agency, projects
from app.services.drive import DriveStorage

MAX_BYTES = 5 * 1024 * 1024
TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".txt": "text/plain", ".mp4": "video/mp4"}


def valid_mp4_file(source: BinaryIO, length: int) -> bool:
    offset = 0
    found: set[bytes] = set()
    while offset + 8 <= length:
        source.seek(offset)
        header = source.read(16)
        size = int.from_bytes(header[:4], "big")
        kind = header[4:8]
        header_size = 16 if size == 1 else 8
        if size == 1:
            if len(header) < 16:
                return False
            size = int.from_bytes(header[8:16], "big")
        elif size == 0:
            size = length - offset
        if size < header_size or offset + size > length:
            return False
        if kind == b"ftyp" and offset == 0:
            source.seek(offset + header_size)
            if size < header_size + 8 or source.read(4) not in {b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V "}:
                return False
            found.add(kind)
        if kind in {b"moov", b"mdat"}:
            found.add(kind)
        offset += size
    return offset == length and found == {b"ftyp", b"moov", b"mdat"}


def validate_name(name: str, mime: str) -> None:
    if (
        not name
        or len(name) > 180
        or name.startswith(".")
        or name != name.strip()
        or any(c in "/\\:" or unicodedata.category(c).startswith("C") for c in name)
    ):
        raise HTTPException(422, "Invalid filename")
    if TYPES.get(Path(name).suffix.lower()) != mime:
        raise HTTPException(415, "File extension and media type do not match")


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
    validate_name(name, mime)
    if mime == "video/mp4":
        raise HTTPException(415, "Video requires streaming upload")
    if not body or len(body) > MAX_BYTES:
        raise HTTPException(413, "File exceeds the permitted size")
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


def store_video_file(
    db: Session, actor: UUID, p: Project, name: str, incoming: Path,
    length: int, digest: str, category: Category, visibility: Visibility,
) -> FileAsset:
    validate_name(name, "video/mp4")
    if not length or length > settings().video_max_bytes:
        raise HTTPException(413, "Video exceeds the configured size limit")
    if settings().file_provider != "local":
        raise HTTPException(503, "Video requires local storage")
    with incoming.open("rb") as source:
        if not valid_mp4_file(source, length):
            raise HTTPException(415, "Invalid or incomplete MP4")
    key = uuid4()
    asset = FileAsset(
        id=key, project_id=p.id, client_id=p.client_id, uploaded_by=actor,
        provider="local", file_name=name, mime_type="video/mp4", file_size=length,
        sha256=digest, category=category, visibility=visibility, provider_ref=key.hex,
    )
    db.add(asset)
    db.flush()
    target = Path(settings().storage_dir) / key.hex
    os.replace(incoming, target)
    event.listen(db, "after_rollback", lambda _: target.unlink(missing_ok=True), once=True)
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
        released = (
            select(RevisionFile.file_id)
            .join(Review, Review.revision_id == RevisionFile.revision_id)
            .where(Review.stage == "client")
        )
        released_covers = select(FileAsset.cover_file_id).where(FileAsset.id.in_(released))
        stmt = stmt.where((FileAsset.visibility == "client_visible") | FileAsset.id.in_(released) | FileAsset.id.in_(released_covers))
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
            "cover_file_id",
        )
    }


def archive(db: Session, actor: UUID, key: UUID) -> None:
    row = get(db, actor, key, "agency")
    agency.guard_operational_write(db)
    p = projects.access(db, actor, row.project_id, "agency", write=True)
    if (
        db.scalar(select(FileAsset.id).where(FileAsset.cover_file_id == key).limit(1))
        or
        db.scalar(select(RevisionFile.file_id).where(RevisionFile.file_id == key).limit(1))
        or db.scalar(select(BriefFile.id).where(BriefFile.file_id == key).limit(1))
        or db.scalar(select(SnapshotFile.id).where(SnapshotFile.file_id == key).limit(1))
    ):
        raise HTTPException(409, "Referenced files must be retained")
    row.archived_at = now()
    projects.change_log(db, actor, p, "file.archived", key)


def download(row: FileAsset) -> bytes:
    body = storage(row.provider).read(row.provider_ref or row.id.hex)
    if hashlib.sha256(body).hexdigest() != row.sha256:
        raise HTTPException(503, "Stored file integrity check failed")
    return body


def open_video(row: FileAsset) -> BinaryIO:
    if row.provider != "local":
        raise HTTPException(503, "Video storage unavailable")
    path = Path(settings().storage_dir) / UUID(row.provider_ref or row.id.hex).hex
    source: BinaryIO | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        source = os.fdopen(descriptor, "rb")
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size != row.file_size:
            raise HTTPException(503, "Stored file integrity check failed")
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
        if digest.hexdigest() != row.sha256:
            raise HTTPException(503, "Stored file integrity check failed")
        source.seek(0)
        return source
    except Exception as err:
        if source is not None:
            source.close()
        if isinstance(err, OSError):
            raise HTTPException(503, "File storage unavailable") from err
        raise


def set_video_cover(db: Session, actor: UUID, video_id: UUID, cover_id: UUID, portal: Portal) -> FileAsset:
    video = get(db, actor, video_id, portal)
    cover = get(db, actor, cover_id, portal)
    if video.mime_type != "video/mp4" or cover.mime_type not in {"image/png", "image/jpeg"}:
        raise HTTPException(422, "Choose an MP4 and a PNG or JPEG cover")
    if video.project_id != cover.project_id or video.visibility != cover.visibility:
        raise HTTPException(422, "Cover must share the video's project and visibility")
    projects.access(db, actor, video.project_id, portal, write=True)
    if db.scalar(select(RevisionFile.file_id).where(RevisionFile.file_id == video_id).limit(1)):
        raise HTTPException(409, "Cover is locked after the video is attached to a revision")
    video.cover_file_id = cover.id
    projects.change_log(db, actor, db.get_one(Project, video.project_id), "video.cover_set", video.id, {"cover_file_id": str(cover.id)})
    return video
