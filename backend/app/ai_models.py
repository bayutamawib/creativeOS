from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.brief_models import ProjectRecord, ownership
from app.models import Entity


class Generation(ProjectRecord):
    __tablename__ = "ai_generations"
    snapshot_id: Mapped[UUID]
    generation_type: Mapped[str]
    requester_scope: Mapped[str]
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    service_identity: Mapped[str | None]
    event_id: Mapped[UUID | None] = mapped_column(ForeignKey("outbox_events.id"))
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("workflow_runs.id"))
    idempotency_key: Mapped[str]
    fingerprint: Mapped[str]
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provider: Mapped[str]
    model: Mapped[str]
    prompt_version: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="pending")
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    error_code: Mapped[str | None]
    attempt: Mapped[int] = mapped_column(server_default="0")
    claim_token: Mapped[UUID | None]
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int | None]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    direction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("creative_proposals.id", use_alter=True, name="fk_job_direction")
    )
    revision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("content_revisions.id", use_alter=True, name="fk_job_revision")
    )
    __table_args__ = (
        ownership(),
        ForeignKeyConstraint(
            ["snapshot_id", "project_id"], ["brief_snapshots.id", "brief_snapshots.project_id"]
        ),
        UniqueConstraint("requester_scope", "generation_type", "idempotency_key"),
        UniqueConstraint("id", "snapshot_id"),
        CheckConstraint("(requested_by IS NULL) <> (service_identity IS NULL)"),
        CheckConstraint("status in ('pending','running','completed','failed','cancelled')"),
        Index("generation_due", "status", "next_attempt_at"),
    )


class Proposal(Entity):
    __tablename__ = "creative_proposals"
    generation_id: Mapped[UUID]
    snapshot_id: Mapped[UUID]
    item_index: Mapped[int]
    kind: Mapped[str]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    decision: Mapped[str] = mapped_column(server_default="pending")
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["generation_id", "snapshot_id"], ["ai_generations.id", "ai_generations.snapshot_id"]
        ),
        UniqueConstraint("generation_id", "item_index"),
        CheckConstraint("kind in ('direction','plan_item')"),
        CheckConstraint("decision in ('pending','approved','rejected')"),
    )


class ContentItem(ProjectRecord):
    __tablename__ = "content_items"
    brief_id: Mapped[UUID]
    source_proposal_id: Mapped[UUID] = mapped_column(
        ForeignKey("creative_proposals.id"), unique=True
    )
    title: Mapped[str]
    content_type: Mapped[str]
    channel: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="draft")
    current_revision_id: Mapped[UUID | None]
    __table_args__ = (
        ownership(),
        ForeignKeyConstraint(["brief_id", "project_id"], ["briefs.id", "briefs.project_id"]),
        ForeignKeyConstraint(
            ["id", "current_revision_id"],
            ["content_revisions.content_item_id", "content_revisions.id"],
            name="fk_current_content_revision",
            use_alter=True,
        ),
    )


class ContentRevision(Entity):
    __tablename__ = "content_revisions"
    content_item_id: Mapped[UUID] = mapped_column(ForeignKey("content_items.id"))
    revision_number: Mapped[int]
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    source_generation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_generations.id"))
    __table_args__ = (
        UniqueConstraint("content_item_id", "revision_number"),
        UniqueConstraint("content_item_id", "id"),
        UniqueConstraint("content_item_id", "source_generation_id"),
    )
