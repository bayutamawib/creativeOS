"""CRM and durable workflow records."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Entity


class Lead(Entity):
    __tablename__ = "leads"
    company_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    industry: Mapped[str | None] = mapped_column(String(100))
    service_interest: Mapped[str | None]
    inquiry_message: Mapped[str | None]
    source: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), server_default="new", index=True)
    notes: Mapped[str | None]
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    converted_client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"), unique=True)
    initial_project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "status in ('new','contacted','qualified','proposal_sent','rejected','converted')"
        ),
        CheckConstraint("(status='converted') = (converted_client_id is not null)"),
    )


class ClientInvitation(Entity):
    __tablename__ = "client_invitations"
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    invited_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("role in ('client_admin','client_member')"),)


class Submission(Entity):
    __tablename__ = "external_submissions"
    source: Mapped[str]
    source_submission_id: Mapped[str]
    fingerprint: Mapped[str]
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"))
    __table_args__ = (UniqueConstraint("source", "source_submission_id"),)


class Outbox(Entity):
    __tablename__ = "outbox_events"
    event_type: Mapped[str]
    aggregate_type: Mapped[str]
    aggregate_id: Mapped[UUID]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(server_default="pending")
    attempts: Mapped[int] = mapped_column(server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    claim_token: Mapped[UUID | None]
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("outbox_due", "status", "next_attempt_at"),
        CheckConstraint("status in ('pending','processing','delivered','failed')"),
    )


class WorkflowRun(Entity):
    __tablename__ = "workflow_runs"
    event_id: Mapped[UUID] = mapped_column(ForeignKey("outbox_events.id"))
    workflow_name: Mapped[str]
    workflow_version: Mapped[str]
    n8n_execution_id: Mapped[str]
    attempt: Mapped[int]
    status: Mapped[str] = mapped_column(server_default="running")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None]
    __table_args__ = (UniqueConstraint("event_id", "attempt"),)


class ProcessedEvent(Entity):
    __tablename__ = "processed_events"
    event_id: Mapped[UUID] = mapped_column(ForeignKey("outbox_events.id"))
    consumer_name: Mapped[str]
    result_status: Mapped[str]
    run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id"))
    __table_args__ = (UniqueConstraint("event_id", "consumer_name"),)


class Notification(Entity):
    __tablename__ = "notifications"
    recipient_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("outbox_events.id"))
    channel: Mapped[str]
    deduplication_key: Mapped[str]
    message: Mapped[str]
    delivery_status: Mapped[str]
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("recipient_id", "channel", "deduplication_key"),)
