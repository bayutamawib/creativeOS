from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.brief_models import ProjectRecord, ownership
from app.models import Base


class Report(ProjectRecord):
    __tablename__ = "reports"
    report_type: Mapped[str]
    period_start: Mapped[date]
    period_end: Mapped[date]
    status: Mapped[str]
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB)
    narrative: Mapped[str | None]
    version: Mapped[int] = mapped_column(server_default="1")
    requested_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    service_identity: Mapped[str | None]
    published_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ownership(),
        UniqueConstraint("id", "project_id"),
        UniqueConstraint("project_id", "report_type", "period_start", "period_end"),
        CheckConstraint("period_end >= period_start"),
        CheckConstraint("(requested_by is null) <> (service_identity is null)"),
        CheckConstraint("status in ('generating','draft','ready_for_review','published','failed')"),
        CheckConstraint(
            "(status='published') = (published_at is not null) and (published_at is null) = (published_by is null)"
        ),
    )


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id"), primary_key=True)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), primary_key=True)
