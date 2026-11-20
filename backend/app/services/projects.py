from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Audit, Client, ClientMembership, Project, User
from app.project_inputs import (
    MemberInput,
    MilestoneCreate,
    MilestoneUpdate,
    Portal,
    ProjectCreate,
    ProjectUpdate,
)
from app.project_models import Milestone, ProjectMember
from app.schemas import Input
from app.security import now
from app.services import agency


def effective_portal(db: Session, actor: UUID, portal: Portal | None) -> Portal:
    if portal:
        return portal
    return "agency" if agency.roles(db, actor) else "client"


def scope(db: Session, actor: UUID, portal: Portal) -> Select[Project]:
    stmt = select(Project).where(Project.archived_at.is_(None))
    if portal == "client":
        return stmt.join(ClientMembership, ClientMembership.client_id == Project.client_id).where(
            ClientMembership.user_id == actor, ClientMembership.is_active
        )
    roles = agency.roles(db, actor)
    if roles & {"admin", "agency_manager"}:
        return stmt
    if "team_member" not in roles:
        raise HTTPException(403, "Agency access required")
    return stmt.join(ProjectMember, ProjectMember.project_id == Project.id).where(
        ProjectMember.user_id == actor
    )


def access(
    db: Session, actor: UUID, project_id: UUID, portal: Portal = "agency", *, write: bool = False
) -> Project:
    stmt = scope(db, actor, portal).where(Project.id == project_id)
    if write:
        stmt = stmt.with_for_update(of=Project)
    project = db.scalar(stmt)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


def change_log(
    db: Session,
    actor: UUID,
    project: Project,
    action: str,
    target: UUID,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        Audit(
            actor_id=actor,
            client_id=project.client_id,
            project_id=project.id,
            action=action,
            target_id=target,
            details=details or {},
        )
    )


def project_view(project: Project, portal: Portal) -> dict[str, Any]:
    fields = ["id", "client_id", "name", "status", "start_date", "due_date", "service_type"]
    if portal == "agency":
        fields += ["description", "priority", "budget", "created_by", "updated_at"]
    return {key: getattr(project, key) for key in fields}


def list_view(db: Session, rows: Sequence[Project], portal: Portal) -> list[dict[str, Any]]:
    if not rows:
        return []
    ids = [p.id for p in rows]
    scope = [Milestone.project_id.in_(ids)]
    if portal == "client":
        scope.append(Milestone.client_visible.is_(True))
    counts = {
        pid: (total, done)
        for pid, total, done in db.execute(
            select(
                Milestone.project_id,
                func.count(),
                func.count().filter(Milestone.status == "completed"),
            )
            .where(*scope)
            .group_by(Milestone.project_id)
        )
    }
    # One bounded result per project, including the first undated pending milestone.
    ordered = (
        select(
            Milestone.project_id,
            Milestone.name,
            func.row_number()
            .over(
                partition_by=Milestone.project_id,
                order_by=(Milestone.due_date.nulls_last(), Milestone.created_at, Milestone.id),
            )
            .label("rank"),
        )
        .where(*scope, Milestone.status != "completed")
        .subquery()
    )
    upcoming = {
        pid: name
        for pid, name in db.execute(
            select(ordered.c.project_id, ordered.c.name).where(ordered.c.rank == 1)
        )
    }
    result = []
    for row in rows:
        total, done = counts.get(row.id, (0, 0))
        result.append(
            project_view(row, portal)
            | {"progress": progress_counts(total, done), "next_milestone": upcoming.get(row.id)}
        )
    return result


def changes(data: Input, required: set[str]) -> dict[str, Any]:
    values = data.model_dump(exclude_unset=True)
    if any(values.get(k) is None for k in required & values.keys()):
        raise HTTPException(422, "Required fields cannot be cleared")
    return values


def validate_dates(values: dict[str, Any], current: Any = None) -> None:
    start = values.get("start_date", getattr(current, "start_date", None))
    end = values.get("due_date", getattr(current, "due_date", None))
    if start and end and end < start:
        raise HTTPException(422, "Deadline precedes start date")


def create(db: Session, actor: UUID, data: ProjectCreate) -> Project:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    if db.get(Client, data.client_id) is None:
        raise HTTPException(404, "Client not found")
    values = changes(data, {"name", "priority", "status"})
    validate_dates(values)
    row = Project(**values, created_by=actor)
    db.add(row)
    db.flush()
    change_log(db, actor, row, "project.created", row.id)
    return row


def update(db: Session, actor: UUID, project_id: UUID, data: ProjectUpdate) -> Project:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    row = access(db, actor, project_id, write=True)
    values = changes(data, {"name", "priority", "status"})
    validate_dates(values, row)
    for key, val in values.items():
        setattr(row, key, val)
    db.flush()
    change_log(db, actor, row, "project.updated", row.id, {"fields": sorted(values)})
    return row


def archive(db: Session, actor: UUID, project_id: UUID) -> None:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    row = db.get(Project, project_id, with_for_update=True)
    if row is None:
        raise HTTPException(404, "Project not found")
    if not row.archived_at:
        row.archived_at = now()
        change_log(db, actor, row, "project.archived", row.id)


def members(db: Session, actor: UUID, project_id: UUID) -> list[dict[str, Any]]:
    access(db, actor, project_id)
    return [
        {"user_id": m.user_id, "full_name": name, "project_role": m.project_role}
        for m, name in db.execute(
            select(ProjectMember, User.full_name)
            .join(User)
            .where(ProjectMember.project_id == project_id)
            .order_by(User.full_name)
        )
    ]


def membership(db: Session, project_id: UUID, user_id: UUID) -> ProjectMember | None:
    return db.scalar(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
        )
    )


def set_member(
    db: Session, actor: UUID, project_id: UUID, data: MemberInput, *, remove: bool = False
) -> None:
    agency.guard(db)
    agency.manager_roles(db, actor)
    row = access(db, actor, project_id, write=True)
    entry = membership(db, project_id, data.user_id)
    if remove:
        if entry is None:
            return
        db.delete(entry)
    else:
        if not agency.roles(db, data.user_id):
            raise HTTPException(422, "Active agency member required")
        if entry is None:
            db.add(
                ProjectMember(
                    project_id=project_id, user_id=data.user_id, project_role=data.project_role
                )
            )
        elif entry.project_role != data.project_role:
            entry.project_role = data.project_role
        else:
            return
    change_log(
        db,
        actor,
        row,
        "project_member.removed" if remove else "project_member.assigned",
        data.user_id,
    )


def milestones(db: Session, project_id: UUID, portal: Portal) -> Sequence[Milestone]:
    stmt = select(Milestone).where(Milestone.project_id == project_id)
    if portal == "client":
        stmt = stmt.where(Milestone.client_visible)
    return db.scalars(
        stmt.order_by(Milestone.due_date.nulls_last(), Milestone.created_at, Milestone.id)
    ).all()


def milestone_view(row: Milestone, portal: Portal) -> dict[str, Any]:
    fields = ["id", "name", "status", "due_date", "completed_at"]
    if portal == "agency":
        fields += ["description", "client_visible"]
    return {k: getattr(row, k) for k in fields}


def progress(db: Session, project_id: UUID, portal: Portal) -> dict[str, int]:
    stmt = select(
        func.count(Milestone.id), func.count(Milestone.id).filter(Milestone.status == "completed")
    ).where(Milestone.project_id == project_id)
    if portal == "client":
        stmt = stmt.where(Milestone.client_visible)
    total, done = db.execute(stmt).one()
    return progress_counts(total, done)


def progress_counts(total: int, done: int) -> dict[str, int]:
    return {
        "total_milestones": total,
        "completed_milestones": done,
        "percent": round(100 * done / total) if total else 0,
    }


def save_milestone(
    db: Session,
    actor: UUID,
    project_id: UUID,
    data: MilestoneCreate | MilestoneUpdate,
    identifier: UUID | None = None,
) -> Milestone:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    project = access(db, actor, project_id, write=True)
    row = db.get(Milestone, identifier) if identifier else Milestone(project_id=project.id)
    if row is None or row.project_id != project.id:
        raise HTTPException(404, "Milestone not found")
    values = changes(data, {"name", "status", "client_visible"})
    if "status" in values and values["status"] != row.status:
        row.completed_at = now() if values["status"] == "completed" else None
    for key, val in values.items():
        setattr(row, key, val)
    db.add(row)
    db.flush()
    change_log(
        db,
        actor,
        project,
        "milestone.updated" if identifier else "milestone.created",
        row.id,
        {"fields": sorted(values)},
    )
    return row
