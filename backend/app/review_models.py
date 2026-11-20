from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, Entity


def revision_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["content_item_id", "revision_id"],
        ["content_revisions.content_item_id", "content_revisions.id"],
    )


class Review(Entity):
    __tablename__ = "content_approvals"
    content_item_id: Mapped[UUID]
    revision_id: Mapped[UUID]
    stage: Mapped[str]
    decision: Mapped[str] = mapped_column(server_default="pending")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    membership_id: Mapped[UUID | None] = mapped_column(ForeignKey("client_memberships.id"))
    delegation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("project_approval_delegations.id")
    )
    __table_args__ = (
        revision_fk(),
        UniqueConstraint("revision_id", "stage"),
        CheckConstraint("stage in ('client','internal')"),
        CheckConstraint(
            "(decision in ('pending','superseded') and decided_by is null and decided_at is null) or (decision in ('approved','revision_requested','rejected') and decided_by is not null and decided_at is not null)"
        ),
    )


class Feedback(Entity):
    __tablename__ = "content_feedback"
    content_item_id: Mapped[UUID]
    revision_id: Mapped[UUID]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    visibility: Mapped[str]
    message: Mapped[str]
    __table_args__ = (revision_fk(), CheckConstraint("visibility in ('client_visible','internal')"))


class RevisionFile(Base):
    __tablename__ = "revision_files"
    revision_id: Mapped[UUID] = mapped_column(ForeignKey("content_revisions.id"), primary_key=True)
    file_id: Mapped[UUID] = mapped_column(ForeignKey("file_assets.id"), primary_key=True)
