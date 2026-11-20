from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Entity


class ProjectMember(Entity):
    __tablename__ = "project_members"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    project_role: Mapped[str | None]
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)


class Milestone(Entity):
    __tablename__ = "milestones"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    description: Mapped[str | None]
    due_date: Mapped[date | None]
    status: Mapped[str] = mapped_column(server_default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_visible: Mapped[bool] = mapped_column(server_default=text("false"))
    __table_args__ = (
        UniqueConstraint("id", "project_id"),
        CheckConstraint("status in ('pending','in_progress','completed','blocked')"),
    )


class Task(Entity):
    __tablename__ = "tasks"
    project_id: Mapped[UUID] = mapped_column(index=True)
    client_id: Mapped[UUID]
    milestone_id: Mapped[UUID | None]
    title: Mapped[str]
    description: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default="todo")
    priority: Mapped[str] = mapped_column(server_default="medium")
    start_date: Mapped[date | None]
    due_date: Mapped[date | None] = mapped_column(index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("id", "project_id"),
        ForeignKeyConstraint(["project_id", "client_id"], ["projects.id", "projects.client_id"]),
        ForeignKeyConstraint(
            ["milestone_id", "project_id"], ["milestones.id", "milestones.project_id"]
        ),
        CheckConstraint("due_date >= start_date"),
        CheckConstraint(
            "status in ('todo','in_progress','in_review','completed','blocked','cancelled')"
        ),
        CheckConstraint("priority in ('low','medium','high','urgent')"),
    )


class TaskAssignee(Entity):
    __tablename__ = "task_assignees"
    project_id: Mapped[UUID]
    task_id: Mapped[UUID]
    user_id: Mapped[UUID]
    __table_args__ = (
        UniqueConstraint("task_id", "user_id"),
        ForeignKeyConstraint(["task_id", "project_id"], ["tasks.id", "tasks.project_id"]),
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["project_members.project_id", "project_members.user_id"],
            ondelete="CASCADE",
        ),
    )
