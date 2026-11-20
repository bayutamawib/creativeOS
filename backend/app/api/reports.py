import json
from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import Database, Identity
from app.api.projects import Page, PageSize
from app.models import Project, User
from app.operations_models import WorkflowRun
from app.project_inputs import Portal
from app.project_models import Task, TaskAssignee
from app.report_models import Report
from app.schemas import Input
from app.services import agency, projects, reports

router = APIRouter()


class Period(Input):
    period_start: date
    period_end: date
    report_type: Literal["weekly", "project"] = "project"


class Version(Input):
    version: int = Field(ge=1)


class Edit(Version):
    narrative: str = Field(min_length=1, max_length=12000)


@router.post("/projects/{project_id}/reports/generate", status_code=202)
def generate(project_id: UUID, data: Period, db: Database, identity: Identity) -> dict[str, Any]:
    project = projects.access(db, identity.user_id, project_id)
    row = reports.generate(
        db, project, data.period_start, data.period_end, data.report_type, actor=identity.user_id
    )
    return {"data": reports.view(row)}


@router.get("/reports")
@router.get("/projects/{project_id}/reports")
def listing(
    db: Database,
    identity: Identity,
    project_id: UUID | None = None,
    portal: Portal | None = None,
    page: Page = 1,
    page_size: PageSize = 50,
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    stmt = (
        reports.scoped(db, identity.user_id, mode)
        .add_columns(Project.name)
        .join(Project, Project.id == Report.project_id)
    )
    if project_id:
        projects.access(db, identity.user_id, project_id, mode)
        stmt = stmt.where(Report.project_id == project_id)
    rows = db.execute(
        stmt.order_by(Report.created_at.desc(), Report.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": [reports.view(r) | {"project_name": name} for r, name in rows]}


@router.get("/reports/{report_id}")
def detail(
    report_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    return {"data": reports.view(reports.get(db, identity.user_id, report_id, mode))}


@router.get("/reports/{report_id}/download")
def download(
    report_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> Response:
    data = detail(report_id, db, identity, portal)["data"]
    return Response(
        json.dumps(data, default=str, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="project-report-{report_id}.json"'},
    )


@router.patch("/reports/{report_id}")
def edit(report_id: UUID, data: Edit, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": reports.view(
            reports.transition(
                db, identity.user_id, report_id, data.version, "edit", data.narrative
            )
        )
    }


@router.post("/reports/{report_id}/submit-for-review")
def submit(report_id: UUID, data: Version, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": reports.view(
            reports.transition(db, identity.user_id, report_id, data.version, "submit")
        )
    }


@router.post("/reports/{report_id}/publish")
def publish(report_id: UUID, data: Version, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": reports.view(
            reports.transition(db, identity.user_id, report_id, data.version, "publish")
        )
    }


@router.get("/agency/reports/{kind}")
def analytics(
    kind: Literal["operations", "workload", "workflows"], db: Database, identity: Identity
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    if kind == "operations":
        stmt = (
            select(Project.status, func.count())
            .where(Project.archived_at.is_(None))
            .group_by(Project.status)
        )
    elif kind == "workflows":
        stmt = select(WorkflowRun.status, func.count()).group_by(WorkflowRun.status)
    else:
        stmt = (
            select(User.full_name, func.count())
            .select_from(TaskAssignee)
            .join(User, User.id == TaskAssignee.user_id)
            .join(Task, Task.id == TaskAssignee.task_id)
            .join(Project, Project.id == Task.project_id)
            .where(Project.archived_at.is_(None), Task.status.notin_(["completed", "cancelled"]))
            .group_by(User.id, User.full_name)
        )
    return {
        "data": [
            {"label": label, "count": count}
            for label, count in db.execute(stmt.order_by(stmt.selected_columns[0]))
        ]
    }
