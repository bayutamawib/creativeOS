from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Entity


class ProjectRecord(Entity):
    __abstract__ = True
    project_id: Mapped[UUID] = mapped_column(index=True)
    client_id: Mapped[UUID]


def ownership() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["project_id", "client_id"], ["projects.id", "projects.client_id"])


class FileAsset(ProjectRecord):
    __tablename__ = "file_assets"
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider_ref: Mapped[str | None]
    provider: Mapped[str]
    file_name: Mapped[str]
    mime_type: Mapped[str]
    file_size: Mapped[int]
    sha256: Mapped[str]
    category: Mapped[str]
    visibility: Mapped[str]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ownership(),
        UniqueConstraint("id", "project_id"),
        CheckConstraint("visibility in ('internal','client_visible')"),
    )


class Brief(ProjectRecord):
    __tablename__ = "briefs"
    title: Mapped[str]
    objective: Mapped[str]
    requirements: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(server_default="draft")
    version: Mapped[int] = mapped_column(server_default="1")
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    submitted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    feedback: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        ownership(),
        UniqueConstraint("id", "project_id"),
        CheckConstraint(
            "status in ('draft','submitted','under_review','revision_requested','approved','rejected')"
        ),
    )


class BriefFile(Entity):
    __tablename__ = "brief_files"
    project_id: Mapped[UUID]
    brief_id: Mapped[UUID]
    file_id: Mapped[UUID]
    __table_args__ = (
        ForeignKeyConstraint(["brief_id", "project_id"], ["briefs.id", "briefs.project_id"]),
        ForeignKeyConstraint(
            ["file_id", "project_id"], ["file_assets.id", "file_assets.project_id"]
        ),
        UniqueConstraint("brief_id", "file_id"),
    )


class Snapshot(ProjectRecord):
    __tablename__ = "brief_snapshots"
    brief_id: Mapped[UUID]
    version: Mapped[int]
    approved_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB)
    brand: Mapped[dict[str, Any]] = mapped_column(JSONB)
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    __table_args__ = (
        ownership(),
        ForeignKeyConstraint(["brief_id", "project_id"], ["briefs.id", "briefs.project_id"]),
        UniqueConstraint("brief_id", "version"),
        UniqueConstraint("id", "project_id"),
    )


class SnapshotFile(Entity):
    __tablename__ = "snapshot_files"
    project_id: Mapped[UUID]
    snapshot_id: Mapped[UUID]
    file_id: Mapped[UUID]
    __table_args__ = (
        ForeignKeyConstraint(
            ["snapshot_id", "project_id"], ["brief_snapshots.id", "brief_snapshots.project_id"]
        ),
        ForeignKeyConstraint(
            ["file_id", "project_id"], ["file_assets.id", "file_assets.project_id"]
        ),
        UniqueConstraint("snapshot_id", "file_id"),
    )
