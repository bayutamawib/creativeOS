from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Audit, Client, ClientMembership, Delegation, Project, User
from app.security import now
from app.services.agency import manager_roles


def membership(
    db: Session, actor: UUID, client_id: UUID, *, lock: bool = False
) -> ClientMembership:
    stmt = (
        select(ClientMembership)
        .join(User)
        .where(
            User.id == actor,
            User.is_active,
            ClientMembership.is_active,
            ClientMembership.client_id == client_id,
        )
    )
    if lock:
        stmt = stmt.with_for_update(read=True)
    result = db.scalar(stmt)
    if not result:
        raise HTTPException(404, "Resource not found")
    return result


def project_context(
    db: Session, actor: UUID, project_id: UUID, *, lock: bool = False
) -> tuple[Project, ClientMembership]:
    stmt = (
        select(Project)
        .join(ClientMembership, ClientMembership.client_id == Project.client_id)
        .where(
            Project.archived_at.is_(None),
            Project.id == project_id,
            ClientMembership.user_id == actor,
            ClientMembership.is_active,
        )
    )
    if lock:
        stmt = stmt.with_for_update(of=Project)
    project = db.scalar(stmt)
    if not project:
        raise HTTPException(404, "Resource not found")
    return project, membership(db, actor, project.client_id, lock=lock)


def projects(db: Session, actor: UUID, client_id: UUID) -> list[dict[str, Any]]:
    membership(db, actor, client_id)
    return [
        {"id": p.id, "name": p.name}
        for p in db.scalars(
            select(Project)
            .where(Project.client_id == client_id, Project.archived_at.is_(None))
            .order_by(Project.name)
        )
    ]


def profile(db: Session, actor: UUID, client_id: UUID, *, portal: str) -> dict[str, Any]:
    if portal == "agency":
        manager_roles(db, actor)
    else:
        membership(db, actor, client_id)
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, "Resource not found")
    return {"id": client.id, "company_name": client.company_name}


def active_grant(db: Session, project: Project, member: ClientMembership) -> Delegation | None:
    return db.scalar(
        select(Delegation).where(
            Delegation.project_id == project.id,
            Delegation.grantee_membership_id == member.id,
            Delegation.revoked_at.is_(None),
        )
    )


def authority(db: Session, actor: UUID, project_id: UUID) -> dict[str, Any]:
    project, member = project_context(db, actor, project_id, lock=True)
    admin = member.role == "client_admin"
    return {
        "project_id": project.id,
        "name": project.name,
        "client_id": project.client_id,
        "can_manage_delegations": admin,
        "has_binding_authority": admin or active_grant(db, project, member) is not None,
    }


def require_admin(member: ClientMembership) -> None:
    if member.role != "client_admin":
        raise HTTPException(403, "Client Admin required")


def grant_list(db: Session, actor: UUID, project_id: UUID) -> list[dict[str, Any]]:
    project, member = project_context(db, actor, project_id)
    require_admin(member)
    rows = db.execute(
        select(ClientMembership, User.full_name)
        .join(User)
        .where(
            ClientMembership.client_id == project.client_id,
            ClientMembership.role == "client_member",
            ClientMembership.is_active,
            User.is_active,
        )
        .order_by(User.full_name)
    )
    grants = set(
        db.scalars(
            select(Delegation.grantee_membership_id).where(
                Delegation.project_id == project_id, Delegation.revoked_at.is_(None)
            )
        )
    )
    return [{"membership_id": m.id, "name": name, "delegated": m.id in grants} for m, name in rows]


def change_grant(db: Session, actor: UUID, project_id: UUID, target: UUID, grant: bool) -> None:
    project, admin = project_context(db, actor, project_id, lock=True)
    require_admin(admin)
    row = db.execute(
        select(ClientMembership, User.is_active)
        .join(User)
        .where(ClientMembership.id == target, ClientMembership.client_id == project.client_id)
        .with_for_update(read=True)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Resource not found")
    member, user_active = row
    prior = active_grant(db, project, member)
    if grant:
        if member.role != "client_member" or not member.is_active or not user_active:
            raise HTTPException(403, "An active Client Member is required")
        if prior:
            return
        record = Delegation(
            client_id=project.client_id,
            project_id=project.id,
            grantee_membership_id=member.id,
            granted_by_membership_id=admin.id,
        )
        db.add(record)
        db.flush()
    elif prior:
        record = prior
        record.revoked_at, record.revoked_by_membership_id = now(), admin.id
    else:
        return
    db.add(
        Audit(
            actor_id=actor,
            action="delegation.granted" if grant else "delegation.revoked",
            target_id=record.id,
            client_id=project.client_id,
            project_id=project.id,
            details={"grantee_membership_id": str(target)},
        )
    )
