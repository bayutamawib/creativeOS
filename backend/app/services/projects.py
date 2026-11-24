from collections.abc import Sequence
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session, aliased

from app.brief_models import FileAsset
from app.models import (
    Audit,
    Client,
    ClientMembership,
    OperationsSettings,
    Project,
    User,
)
from app.project_inputs import (
    MemberInput,
    MilestoneCreate,
    MilestoneUpdate,
    Portal,
    ProjectCreate,
    ProjectUpdate,
)
from app.project_models import Milestone, ProjectMember, Task, TaskAssignee
from app.schemas import Input
from app.security import now
from app.services import agency

CLIENT_ACTIVITY_ACTIONS = {
    "project.created",
    "project.updated",
    "content.approve-and-release",
    "content.client-approval",
    "content.request-revision",
}
TEAM_ACTIVITY_ACTIONS = {
    "project.created",
    "project.updated",
    "project_member.assigned",
    "project_member.removed",
    "milestone.created",
    "milestone.updated",
}


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


def _activity_description(
    action: str,
    details: dict[str, Any],
    task_name: str | None,
    milestone_name: str | None,
    person_name: str | None,
) -> str:
    if action == "project.created":
        return "Created the project"
    if action == "project.updated":
        return "Updated the project"
    if action == "project.archived":
        return "Archived the project"
    if action == "project_member.assigned":
        return f"Added {person_name or 'a team member'} to the project"
    if action == "project_member.removed":
        return f"Removed {person_name or 'a team member'} from the project"
    if action == "milestone.created":
        return f"Created milestone “{milestone_name or 'Unavailable milestone'}”"
    if action == "milestone.updated":
        return f"Updated milestone “{milestone_name or 'Unavailable milestone'}”"
    if action == "task.created":
        return f"Created task “{task_name or 'Unavailable task'}”"
    if action == "task.assigned":
        return f"Assigned {person_name or 'a team member'} to “{task_name or 'Unavailable task'}”"
    if action == "task.unassigned":
        return f"Unassigned {person_name or 'a team member'} from “{task_name or 'Unavailable task'}”"
    if action == "task.updated":
        before, after = details.get("from"), details.get("to")
        if before and after and before != after:
            return (
                f"Moved “{task_name or 'Unavailable task'}” from "
                f"{str(before).replace('_', ' ')} to {str(after).replace('_', ' ')}"
            )
        return f"Updated task “{task_name or 'Unavailable task'}”"
    if action == "task_template.applied":
        return f"Applied a task template with {details.get('task_count', 0)} planned tasks"
    labels = {
        "content.submit-for-internal-review": "Submitted content for internal review",
        "content.request-internal-changes": "Requested internal content changes",
        "content.approve-and-release": "Approved and released content for client review",
        "content.client-approval": "Approved released content",
        "content.request-revision": "Requested a content revision",
        "content.feedback": "Added content feedback",
    }
    return labels.get(action, action.replace(".", " · ").replace("_", " ").capitalize())


def activity(
    db: Session,
    actor: UUID,
    project_id: UUID,
    portal: Portal,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    project = access(db, actor, project_id, portal)
    query = select(Audit).where(Audit.project_id == project.id)
    roles = agency.roles(db, actor) if portal == "agency" else set()
    if portal == "client":
        visible_milestones = select(Milestone.id).where(
            Milestone.project_id == project.id, Milestone.client_visible.is_(True)
        )
        query = query.where(
            Audit.action.in_(CLIENT_ACTIVITY_ACTIONS)
            | (
                Audit.action.in_({"milestone.created", "milestone.updated"})
                & Audit.target_id.in_(visible_milestones)
            )
        )
    elif not roles & {"admin", "agency_manager"}:
        assigned_tasks = (
            select(Task.id)
            .join(TaskAssignee, TaskAssignee.task_id == Task.id)
            .where(Task.project_id == project.id, TaskAssignee.user_id == actor)
        )
        query = query.where(
            Audit.action.in_(TEAM_ACTIVITY_ACTIONS)
            | (Audit.action.like("task.%") & Audit.target_id.in_(assigned_tasks))
        )
    rows = db.scalars(
        query.order_by(Audit.created_at.desc(), Audit.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    ).all()
    has_more = len(rows) > page_size
    rows = rows[:page_size]
    target_ids = {row.target_id for row in rows}
    user_ids = {row.actor_id for row in rows if row.actor_id}
    user_ids.update(
        UUID(value)
        for row in rows
        if (value := row.details.get("user_id"))
        and isinstance(value, str)
        and _is_uuid(value)
    )
    users = dict(
        db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    )
    tasks = dict(
        db.execute(select(Task.id, Task.title).where(Task.id.in_(target_ids))).all()
    )
    milestone_names = dict(
        db.execute(select(Milestone.id, Milestone.name).where(Milestone.id.in_(target_ids))).all()
    )
    client_people = (
        set(
            db.scalars(
                select(ClientMembership.user_id).where(
                    ClientMembership.client_id == project.client_id,
                    ClientMembership.is_active.is_(True),
                )
            )
        )
        if portal == "client"
        else set()
    )
    timezone = db.get(OperationsSettings, 1)
    items = []
    for row in rows:
        related_user = row.details.get("user_id")
        related_name = users.get(UUID(related_user)) if _is_uuid(related_user) else None
        if portal == "client":
            actor_name = users.get(row.actor_id) if row.actor_id in client_people else "Creative team"
        else:
            actor_name = users.get(row.actor_id, "Former user") if row.actor_id else "System"
        items.append(
            {
                "id": row.id,
                "type": row.action,
                "occurred_at": row.created_at,
                "actor": actor_name,
                "description": _activity_description(
                    row.action,
                    row.details,
                    tasks.get(row.target_id),
                    milestone_names.get(row.target_id),
                    related_name or users.get(row.target_id),
                ),
            }
        )
    return {
        "items": items,
        "page": page,
        "has_more": has_more,
        "timezone": timezone.timezone if timezone else "Asia/Jakarta",
    }


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError, AttributeError):
        return False


def project_view(project: Project, portal: Portal) -> dict[str, Any]:
    fields = ["id", "client_id", "name", "status", "start_date", "due_date", "service_type"]
    if portal == "agency":
        fields += ["description", "priority", "budget", "created_by", "updated_at"]
    return {key: getattr(project, key) for key in fields}


def list_view(
    db: Session, rows: Sequence[Project], portal: Portal, actor: UUID
) -> list[dict[str, Any]]:
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
    # Reuse file scope so client cards include only shared or released media.
    from app.services import assets

    covering_video = aliased(FileAsset)
    cover_rows = db.execute(
        assets.visible(db, actor, portal)
        .where(
            FileAsset.project_id.in_(ids),
            FileAsset.mime_type.in_(["image/png", "image/jpeg", "video/mp4"]),
            ~FileAsset.id.in_(
                select(covering_video.cover_file_id).where(
                    covering_video.cover_file_id.is_not(None),
                    covering_video.archived_at.is_(None),
                )
            ),
        )
        .order_by(FileAsset.project_id, FileAsset.created_at.desc(), FileAsset.id)
        .ext(distinct_on(FileAsset.project_id))
    ).scalars()
    covers = {f.project_id: f for f in cover_rows}
    client_names = (
        dict(
            db.execute(
                select(Client.id, Client.company_name).where(
                    Client.id.in_({r.client_id for r in rows})
                )
            ).all()
        )
        if portal == "agency"
        else {}
    )
    result = []
    for row in rows:
        total, done = counts.get(row.id, (0, 0))
        result.append(
            project_view(row, portal)
            | {
                "progress": progress_counts(total, done),
                "next_milestone": upcoming.get(row.id),
                "cover_file_id": (covers[row.id].cover_file_id if covers[row.id].mime_type == "video/mp4" else covers[row.id].id) if row.id in covers else None,
                "cover_video_id": covers[row.id].id if row.id in covers and covers[row.id].mime_type == "video/mp4" else None,
                **({"client_name": client_names.get(row.client_id)} if portal == "agency" else {}),
            }
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
