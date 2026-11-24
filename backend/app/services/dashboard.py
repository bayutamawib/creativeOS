from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai_models import ContentItem
from app.brief_models import Brief
from app.models import ClientMembership, Project, User
from app.project_models import Milestone, Task, TaskAssignee
from app.review_models import Review
from app.security import now
from app.services import projects, tasks
from app.services.reminders import day


def agency(db: Session, actor: UUID) -> dict[str, Any]:
    visible_projects = projects.scope(db, actor, "agency").with_only_columns(Project.id)
    visible_tasks = tasks.task_scope(db, actor).with_only_columns(Task.id)
    active_states = {"draft", "planning", "in_progress", "in_review", "on_hold"}
    active_projects = db.scalar(
        select(func.count()).select_from(Project).where(
            Project.id.in_(visible_projects), Project.status.in_(active_states)
        )
    ) or 0
    today = day(now())
    task_counts = db.execute(
        select(
            func.count().filter(Task.status.notin_(["completed", "cancelled"])),
            func.count().filter(
                Task.due_date < today,
                Task.status.notin_(["completed", "cancelled"]),
            ),
            func.count().filter(Task.status == "completed"),
            func.count().filter(Task.status != "cancelled"),
        ).where(Task.id.in_(visible_tasks))
    ).one()
    open_tasks, overdue_tasks, completed_tasks, measured_tasks = task_counts
    workload = [
        {
            "assignee": name,
            "open_tasks": open_count,
            "overdue_tasks": overdue_count,
        }
        for name, open_count, overdue_count in db.execute(
            select(
                User.full_name,
                func.count(Task.id),
                func.count(Task.id).filter(Task.due_date < today),
            )
            .join(TaskAssignee, TaskAssignee.user_id == User.id)
            .join(Task, Task.id == TaskAssignee.task_id)
            .where(
                Task.id.in_(visible_tasks),
                Task.status.notin_(["completed", "cancelled"]),
            )
            .group_by(User.id, User.full_name)
            .order_by(func.count(Task.id).desc(), User.full_name)
        )
    ]
    unassigned, unassigned_overdue = db.execute(
        select(
            func.count(),
            func.count().filter(Task.due_date < today),
        )
        .select_from(Task)
        .where(
            Task.id.in_(visible_tasks),
            Task.status.notin_(["completed", "cancelled"]),
            ~Task.id.in_(select(TaskAssignee.task_id)),
        )
    ).one()
    if unassigned:
        workload.append(
            {
                "assignee": "Unassigned",
                "open_tasks": unassigned,
                "overdue_tasks": unassigned_overdue,
            }
        )
    project_rows = db.execute(
        select(
            Project.id,
            Project.name,
            Project.status,
            func.count(Milestone.id),
            func.count(Milestone.id).filter(Milestone.status == "completed"),
        )
        .outerjoin(Milestone, Milestone.project_id == Project.id)
        .where(Project.id.in_(visible_projects), Project.status.in_(active_states))
        .group_by(Project.id)
        .order_by(Project.updated_at.desc(), Project.id)
        .limit(10)
    )
    return {
        "active_projects": active_projects,
        "open_tasks": open_tasks,
        "overdue_tasks": overdue_tasks,
        "task_completion_rate": round(100 * completed_tasks / measured_tasks)
        if measured_tasks
        else 0,
        "workload": workload,
        "projects": [
            {
                "id": project_id,
                "name": name,
                "status": status,
                "progress": round(100 * done / total) if total else 0,
            }
            for project_id, name, status, total, done in project_rows
        ],
    }


def client(db: Session, actor: UUID, client_id: UUID) -> dict[str, Any]:
    membership = db.scalar(
        select(ClientMembership).where(
            ClientMembership.client_id == client_id,
            ClientMembership.user_id == actor,
            ClientMembership.is_active.is_(True),
        )
    )
    if not membership:
        raise HTTPException(404, "Client workspace not found")
    rows = db.scalars(
        projects.scope(db, actor, "client")
        .where(Project.client_id == client_id)
        .order_by(Project.updated_at.desc(), Project.id)
    ).all()
    project_ids = [row.id for row in rows]
    briefs = db.execute(
        select(Brief.id, Brief.project_id, Brief.title, Brief.status)
        .where(Brief.project_id.in_(project_ids))
        .order_by(Brief.updated_at.desc(), Brief.id)
    )
    milestones = db.execute(
        select(Milestone.project_id, Milestone.name, Milestone.status, Milestone.due_date)
        .where(Milestone.project_id.in_(project_ids), Milestone.client_visible.is_(True))
        .order_by(Milestone.due_date.nulls_last(), Milestone.created_at, Milestone.id)
    )
    approvals = db.execute(
        select(ContentItem.id, ContentItem.project_id, ContentItem.title)
        .join(
            Review,
            (Review.content_item_id == ContentItem.id)
            & (Review.revision_id == ContentItem.current_revision_id),
        )
        .where(
            ContentItem.project_id.in_(project_ids),
            Review.stage == "client",
            Review.decision == "pending",
        )
        .order_by(ContentItem.created_at.desc(), ContentItem.id)
    )
    return {
        "projects": projects.list_view(db, rows, "client", actor),
        "briefs": [
            {"id": key, "project_id": project_id, "title": title, "status": status}
            for key, project_id, title, status in briefs
        ],
        "milestones": [
            {
                "project_id": project_id,
                "name": name,
                "status": status,
                "due_date": due_date,
            }
            for project_id, name, status, due_date in milestones
        ],
        "pending_approvals": [
            {"id": key, "project_id": project_id, "title": title}
            for key, project_id, title in approvals
        ],
    }
