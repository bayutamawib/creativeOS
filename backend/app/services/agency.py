import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app.models import (
    AgencyInvitation,
    AgencyMembership,
    Audit,
    BrowserSession,
    OperationsSettings,
    User,
)
from app.schemas import AgencyRole, Invite, Redeem
from app.security import digest, hash_password, now


def guard(db: Session) -> None:
    # Single agency. All writers take this lock before reading actor or target privileges.
    db.execute(text("SELECT pg_advisory_xact_lock(148992357)"))


def guard_operational_write(db: Session) -> None:
    # Concurrent operational writes may proceed while the agency role set is stable.
    db.execute(text("SELECT pg_advisory_xact_lock_shared(148992357)"))


def roles(db: Session, user_id: UUID, *, active_only: bool = True) -> set[str]:
    stmt = select(AgencyMembership.role).join(User).where(AgencyMembership.user_id == user_id)
    if active_only:
        stmt = stmt.where(User.is_active, AgencyMembership.is_active)
    return set(db.scalars(stmt))


def manager_roles(db: Session, actor: UUID) -> set[str]:
    active = roles(db, actor)
    if not active.intersection({"admin", "agency_manager"}):
        raise HTTPException(403, "Agency management permission required")
    return active


def authorize_target(db: Session, actor: UUID, target: UUID | None, role: AgencyRole) -> None:
    active = manager_roles(db, actor)
    if "admin" in active:
        return
    elevated = target is not None and roles(db, target, active_only=False).intersection(
        {"admin", "agency_manager"}
    )
    if role != AgencyRole.TEAM or actor == target or elevated:
        raise HTTPException(403, "Insufficient membership authority")


def audit(db: Session, actor: UUID, action: str, target: UUID, details: dict[str, Any]) -> None:
    db.add(Audit(actor_id=actor, action=action, target_id=target, details=details))


def preserve_admin(db: Session) -> None:
    count = db.scalar(
        select(func.count())
        .select_from(AgencyMembership)
        .join(User)
        .where(User.is_active, AgencyMembership.is_active, AgencyMembership.role == "admin")
    )
    if not count:
        raise HTTPException(409, "The agency must retain an active Admin")


def change_role(
    db: Session, actor: UUID, target: UUID, role: AgencyRole, operation: str, active: bool = True
) -> None:
    guard(db)
    authorize_target(db, actor, target, role)
    if db.get(User, target) is None:
        raise HTTPException(404, "Member not found")
    membership = db.scalar(
        select(AgencyMembership).where(
            AgencyMembership.user_id == target, AgencyMembership.role == role
        )
    )
    before = membership.is_active if membership else None
    if operation == "revoke":
        if membership is None:
            return
        db.delete(membership)
        after = None
    else:
        if membership is None:
            if operation == "activate":
                raise HTTPException(404, "Membership not found")
            db.add(AgencyMembership(user_id=target, role=role.value, is_active=active))
        elif membership.is_active == active:
            return
        else:
            membership.is_active = active
        after = active
    db.flush()
    if role == AgencyRole.ADMIN:
        preserve_admin(db)
    audit(
        db,
        actor,
        "agency_membership." + operation,
        target,
        {"role": role.value, "before_active": before, "after_active": after},
    )


def set_account_active(db: Session, actor: UUID, target: UUID, active: bool) -> None:
    guard(db)
    if "admin" not in manager_roles(db, actor):
        raise HTTPException(403, "Admin required")
    user = db.get(User, target)
    if user is None:
        raise HTTPException(404, "Member not found")
    if user.is_active == active:
        return
    user.is_active = active
    db.flush()
    preserve_admin(db)
    if not active:
        db.execute(
            update(BrowserSession)
            .where(BrowserSession.user_id == target, BrowserSession.revoked_at.is_(None))
            .values(revoked_at=now())
        )
    audit(
        db,
        actor,
        "account.activation",
        target,
        {"before_active": not active, "after_active": active},
    )


def issue_invite(db: Session, actor: UUID, payload: Invite) -> dict[str, Any]:
    guard(db)
    email = str(payload.email).lower()
    target = db.scalar(select(User.id).where(User.email == email))
    authorize_target(db, actor, target, payload.role)
    token = secrets.token_urlsafe(40)
    invite = AgencyInvitation(
        email=email,
        role=payload.role.value,
        invited_by=actor,
        token_digest=digest(token),
        expires_at=now() + timedelta(days=2),
    )
    db.add(invite)
    db.flush()
    audit(db, actor, "agency_invitation.issued", invite.id, {"role": invite.role})
    return {"id": invite.id, "token": token, "expires_at": invite.expires_at}


def invited_account(db: Session, email: str, payload: Redeem, signed_in: UUID | None) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if not user.is_active or signed_in != user.id:
            raise HTTPException(403, "Sign in to the invited account")
    else:
        if signed_in or not payload.password or not payload.full_name:
            raise HTTPException(400, "Name and password required for a new account")
        user = User(
            email=email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password.get_secret_value()),
        )
        db.add(user)
        db.flush()
    return user


def redeem(db: Session, payload: Redeem, signed_in: UUID | None) -> UUID:
    guard(db)
    invite = db.scalar(
        select(AgencyInvitation).where(
            AgencyInvitation.token_digest == digest(payload.token.get_secret_value())
        )
    )
    if not invite or invite.accepted_at or invite.revoked_at or invite.expires_at <= now():
        raise HTTPException(400, "Invitation unavailable")
    user = db.scalar(select(User).where(User.email == invite.email))
    role = AgencyRole(invite.role)
    authorize_target(db, invite.invited_by, user.id if user else None, role)
    user = invited_account(db, invite.email, payload, signed_in)
    change_role(db, invite.invited_by, user.id, role, "grant")
    invite.accepted_at = now()
    audit(db, user.id, "agency_invitation.accepted", invite.id, {"role": role.value})
    return user.id


def roster(db: Session, actor: UUID) -> list[dict[str, Any]]:
    active = manager_roles(db, actor)
    records: dict[UUID, dict[str, Any]] = {}
    for user, membership in db.execute(
        select(User, AgencyMembership)
        .join(AgencyMembership)
        .order_by(User.full_name, AgencyMembership.role)
    ):
        entry = records.setdefault(
            user.id,
            {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "roles": [],
                "manageable_roles": [],
            },
        )
        entry["roles"].append({"role": membership.role, "is_active": membership.is_active})
    for uid, entry in records.items():
        if "admin" in active:
            entry["manageable_roles"] = list(AgencyRole)
        elif uid != actor and all(m["role"] == "team_member" for m in entry["roles"]):
            entry["manageable_roles"] = ["team_member"]
    return list(records.values())


def operational(db: Session, actor: UUID, timezone: str | None = None) -> str:
    if timezone is not None:
        guard(db)
    manager_roles(db, actor)
    row = db.get(OperationsSettings, 1)
    previous = row.timezone if row else "Asia/Jakarta"
    if timezone is not None and timezone != previous:
        db.merge(OperationsSettings(id=1, timezone=timezone))
        audit(db, actor, "agency_settings.timezone", actor, {"before": previous, "after": timezone})
        return timezone
    return previous
