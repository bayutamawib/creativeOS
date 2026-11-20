from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models import Project, User
from app.operations_models import Outbox
from app.project_inputs import TaskCreate, TaskUpdate
from app.project_models import Milestone, Task, TaskAssignee
from app.security import now
from app.services import agency, projects


def task_scope(db: Session, actor: UUID) -> Select[Task]:
    projects_in_scope = projects.scope(db, actor, "agency").with_only_columns(Project.id)
    stmt = select(Task).where(Task.project_id.in_(projects_in_scope))
    if not agency.roles(db, actor) & {"admin", "agency_manager"}:
        stmt = stmt.join(TaskAssignee, TaskAssignee.task_id == Task.id).where(
            TaskAssignee.user_id == actor
        )
    return stmt


def get(db: Session, actor: UUID, task_id: UUID, *, write: bool = False) -> Task:
    if write:
        agency.guard_operational_write(db)
    query = task_scope(db, actor).where(Task.id == task_id)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Task not found")
    if write:
        # All assignment, membership and task edits serialize on their project.
        projects.access(db, actor, row.project_id, write=True)
        row = db.scalar(query.execution_options(populate_existing=True))
        if row is None:
            raise HTTPException(404, "Task not found")
    return row


def view(db: Session, row: Task) -> dict[str, Any]:
    return views(db, [row])[0]


def views(db: Session, rows: Sequence[Task]) -> list[dict[str, Any]]:
    if not rows:
        return []
    assignees: dict[UUID, list[tuple[UUID, str]]] = {}
    for tid, uid, name in db.execute(
        select(TaskAssignee.task_id, User.id, User.full_name)
        .join(User, User.id == TaskAssignee.user_id)
        .where(TaskAssignee.task_id.in_([t.id for t in rows]))
        .order_by(User.full_name, User.id)
    ):
        assignees.setdefault(tid, []).append((uid, name))
    project_names = {
        pid: name
        for pid, name in db.execute(
            select(Project.id, Project.name).where(Project.id.in_({t.project_id for t in rows}))
        )
    }
    results = []
    for row in rows:
        result = {
            key: getattr(row, key)
            for key in (
                "id",
                "project_id",
                "title",
                "description",
                "milestone_id",
                "status",
                "priority",
                "start_date",
                "due_date",
                "completed_at",
            )
        }
        people = assignees.get(row.id, [])
        result["assignee_ids"] = [uid for uid, _ in people]
        result["assignee_names"] = [name for _, name in people]
        result["project_name"] = project_names[row.project_id]
        results.append(result)
    return results


def validate_milestone(db: Session, project_id: UUID, values: dict[str, Any]) -> None:
    identifier = values.get("milestone_id")
    if identifier:
        row = db.get(Milestone, identifier)
        if row is None or row.project_id != project_id:
            raise HTTPException(422, "Milestone must belong to this project")


def create(db: Session, actor: UUID, project_id: UUID, data: TaskCreate) -> Task:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    project = projects.access(db, actor, project_id, write=True)
    values = projects.changes(data, {"title", "priority", "status"})
    projects.validate_dates(values)
    validate_milestone(db, project_id, values)
    if values.get("status", "todo") != "todo":
        raise HTTPException(422, "New tasks start in todo")
    row = Task(project_id=project_id, client_id=project.client_id, created_by=actor, **values)
    db.add(row)
    db.flush()
    projects.change_log(db, actor, project, "task.created", row.id)
    return row


def update(db: Session, actor: UUID, task_id: UUID, data: TaskUpdate) -> Task:
    row = get(db, actor, task_id, write=True)
    values = projects.changes(data, {"title", "priority", "status"})
    manager = bool(agency.roles(db, actor) & {"admin", "agency_manager"})
    if not manager and values.keys() - {"status"}:
        raise HTTPException(403, "Assigned staff may update task status")
    projects.validate_dates(values, row)
    validate_milestone(db, row.project_id, values)
    status = values.get("status", row.status)
    if status != row.status:
        if row.status in {"completed", "cancelled"} and not (manager and status == "todo"):
            raise HTTPException(409, "Reopen the closed task before changing status")
        if status == "cancelled" and not manager:
            raise HTTPException(403, "Agency management permission required")
        row.completed_at = now() if status == "completed" else None
    before = row.status
    for key, val in values.items():
        setattr(row, key, val)
    db.flush()
    projects.change_log(
        db,
        actor,
        db.get_one(Project, row.project_id),
        "task.updated",
        row.id,
        {"fields": sorted(values), "from": before, "to": status},
    )
    return row


def assign(db: Session, actor: UUID, task_id: UUID, user_id: UUID, *, remove: bool = False) -> None:
    agency.guard(db)
    agency.manager_roles(db, actor)
    row = get(db, actor, task_id, write=True)
    existing = db.scalar(
        select(TaskAssignee).where(TaskAssignee.task_id == task_id, TaskAssignee.user_id == user_id)
    )
    if remove:
        if existing is None:
            return
        db.delete(existing)
    else:
        if not agency.roles(db, user_id) or not projects.membership(db, row.project_id, user_id):
            raise HTTPException(422, "Assign an active member of this project")
        if existing:
            return
        if row.status in {"completed", "cancelled"}:
            raise HTTPException(409, "Task is closed")
        entry = TaskAssignee(task_id=task_id, project_id=row.project_id, user_id=user_id)
        db.add(entry)
        db.flush()
        db.add(
            Outbox(
                event_type="task.assigned",
                aggregate_type="task",
                aggregate_id=task_id,
                payload={"assignment_id": str(entry.id)},
            )
        )
    projects.change_log(
        db,
        actor,
        db.get_one(Project, row.project_id),
        "task.unassigned" if remove else "task.assigned",
        task_id,
        {"user_id": str(user_id)},
    )
