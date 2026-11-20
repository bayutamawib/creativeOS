from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import Database, Identity
from app.models import Project
from app.project_inputs import (
    MemberInput,
    MilestoneCreate,
    MilestoneUpdate,
    Portal,
    ProjectCreate,
    ProjectUpdate,
    TaskAssignment,
    TaskCreate,
    TaskUpdate,
)
from app.project_models import Milestone, Task, TaskAssignee
from app.services import projects, tasks
from app.services.agency import manager_roles

router = APIRouter()
Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]


@router.get("/projects")
def listing(
    db: Database,
    identity: Identity,
    portal: Portal | None = None,
    client_id: UUID | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
    status: str | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, Any]:
    role = projects.effective_portal(db, identity.user_id, portal)
    stmt = projects.scope(db, identity.user_id, role)
    if q.strip():
        stmt = stmt.where(Project.name.icontains(q.strip(), autoescape=True))
    if status:
        stmt = stmt.where(Project.status == status)
    if client_id:
        stmt = stmt.where(Project.client_id == client_id)
    rows = db.scalars(
        stmt.order_by(Project.created_at.desc(), Project.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": projects.list_view(db, rows.all(), role)}


@router.post("/projects", status_code=201)
def create(data: ProjectCreate, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": projects.project_view(projects.create(db, identity.user_id, data), "agency")}


@router.get("/projects/{project_id}")
def detail(
    project_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    role = projects.effective_portal(db, identity.user_id, portal)
    return {
        "data": projects.project_view(projects.access(db, identity.user_id, project_id, role), role)
    }


@router.patch("/projects/{project_id}")
def update(
    project_id: UUID, data: ProjectUpdate, db: Database, identity: Identity
) -> dict[str, Any]:
    return {
        "data": projects.project_view(
            projects.update(db, identity.user_id, project_id, data), "agency"
        )
    }


@router.post("/projects/{project_id}/archive", status_code=204)
def archive(project_id: UUID, db: Database, identity: Identity) -> None:
    projects.archive(db, identity.user_id, project_id)


@router.get("/projects/{project_id}/progress")
def progress(
    project_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    role = projects.effective_portal(db, identity.user_id, portal)
    projects.access(db, identity.user_id, project_id, role)
    return {"data": projects.progress(db, project_id, role)}


@router.get("/projects/{project_id}/members")
def members(project_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": projects.members(db, identity.user_id, project_id)}


@router.post("/projects/{project_id}/members", status_code=204)
def assign_member(project_id: UUID, data: MemberInput, db: Database, identity: Identity) -> None:
    projects.set_member(db, identity.user_id, project_id, data)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: UUID, user_id: UUID, db: Database, identity: Identity) -> None:
    projects.set_member(db, identity.user_id, project_id, MemberInput(user_id=user_id), remove=True)


@router.get("/projects/{project_id}/milestones")
def milestones(
    project_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    role = projects.effective_portal(db, identity.user_id, portal)
    projects.access(db, identity.user_id, project_id, role)
    return {
        "data": [
            projects.milestone_view(row, role) for row in projects.milestones(db, project_id, role)
        ]
    }


@router.post("/projects/{project_id}/milestones", status_code=201)
def add_milestone(
    project_id: UUID, data: MilestoneCreate, db: Database, identity: Identity
) -> dict[str, Any]:
    return {
        "data": projects.milestone_view(
            projects.save_milestone(db, identity.user_id, project_id, data), "agency"
        )
    }


@router.patch("/milestones/{milestone_id}")
def change_milestone(
    milestone_id: UUID, data: MilestoneUpdate, db: Database, identity: Identity
) -> dict[str, Any]:
    manager_roles(db, identity.user_id)
    project_id = db.scalar(select(Milestone.project_id).where(Milestone.id == milestone_id))
    if not project_id:
        raise HTTPException(404, "Milestone not found")
    return {
        "data": projects.milestone_view(
            projects.save_milestone(db, identity.user_id, project_id, data, milestone_id), "agency"
        )
    }


@router.get("/projects/{project_id}/tasks")
def project_tasks(project_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    projects.access(db, identity.user_id, project_id)
    rows = db.scalars(
        tasks.task_scope(db, identity.user_id)
        .where(Task.project_id == project_id)
        .order_by(Task.due_date.nulls_last(), Task.created_at, Task.id)
    )
    return {"data": tasks.views(db, rows.all())}


@router.get("/tasks")
def all_tasks(
    db: Database,
    identity: Identity,
    assignee_id: UUID | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, Any]:
    stmt = tasks.task_scope(db, identity.user_id)
    if assignee_id:
        stmt = stmt.where(
            Task.id.in_(select(TaskAssignee.task_id).where(TaskAssignee.user_id == assignee_id))
        )
    rows = db.scalars(
        stmt.order_by(Task.due_date.nulls_last(), Task.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": tasks.views(db, rows.all())}


@router.post("/projects/{project_id}/tasks", status_code=201)
def add_task(
    project_id: UUID, data: TaskCreate, db: Database, identity: Identity
) -> dict[str, Any]:
    return {"data": tasks.view(db, tasks.create(db, identity.user_id, project_id, data))}


@router.get("/tasks/{task_id}")
def task(task_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": tasks.view(db, tasks.get(db, identity.user_id, task_id))}


@router.patch("/tasks/{task_id}")
def edit_task(task_id: UUID, data: TaskUpdate, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": tasks.view(db, tasks.update(db, identity.user_id, task_id, data))}


@router.post("/tasks/{task_id}/complete")
def complete(task_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": tasks.view(
            db, tasks.update(db, identity.user_id, task_id, TaskUpdate(status="completed"))
        )
    }


@router.post("/tasks/{task_id}/assign", status_code=204)
def assignment(task_id: UUID, data: TaskAssignment, db: Database, identity: Identity) -> None:
    tasks.assign(db, identity.user_id, task_id, data.user_id)


@router.delete("/tasks/{task_id}/assignees/{user_id}", status_code=204)
def unassign(task_id: UUID, user_id: UUID, db: Database, identity: Identity) -> None:
    tasks.assign(db, identity.user_id, task_id, user_id, remove=True)
