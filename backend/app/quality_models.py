from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Entity


class Evaluation(Entity):
    __tablename__ = "ai_evaluations"
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str]
    model: Mapped[str]
    prompt_version: Mapped[str]
    dataset_version: Mapped[str]
    dataset_hash: Mapped[str]
    aggregates: Mapped[dict[str, Any]] = mapped_column(JSONB)


class CaseResult(Entity):
    __tablename__ = "ai_evaluation_cases"
    evaluation_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluations.id"), index=True)
    case_key: Mapped[str]
    service: Mapped[str]
    passed: Mapped[bool]
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB)
    sample: Mapped[dict[str, Any]] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    latency_ms: Mapped[int]
    __table_args__ = (UniqueConstraint("evaluation_id", "case_key"),)


class HumanScore(Entity):
    __tablename__ = "ai_evaluation_reviews"
    case_id: Mapped[UUID] = mapped_column(ForeignKey("ai_evaluation_cases.id"))
    reviewer_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("case_id", "reviewer_id"),)
