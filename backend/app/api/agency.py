from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import Database, Identity
from app.schemas import Activation, AgencyRole, Invite, Operational
from app.services import agency

router = APIRouter(prefix="/agency")


@router.get("/members")
def members(db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": agency.roster(db, identity.user_id)}


@router.post("/invitations", status_code=201)
def invite(payload: Invite, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": agency.issue_invite(db, identity.user_id, payload)}


@router.put("/members/{user_id}/roles/{role}", status_code=204)
def grant(user_id: UUID, role: AgencyRole, db: Database, identity: Identity) -> None:
    agency.change_role(db, identity.user_id, user_id, role, "grant")


@router.patch("/members/{user_id}/roles/{role}", status_code=204)
def activate(
    user_id: UUID, role: AgencyRole, payload: Activation, db: Database, identity: Identity
) -> None:
    agency.change_role(db, identity.user_id, user_id, role, "activate", payload.is_active)


@router.delete("/members/{user_id}/roles/{role}", status_code=204)
def revoke(user_id: UUID, role: AgencyRole, db: Database, identity: Identity) -> None:
    agency.change_role(db, identity.user_id, user_id, role, "revoke")


@router.patch("/members/{user_id}/account", status_code=204)
def set_active(user_id: UUID, payload: Activation, db: Database, identity: Identity) -> None:
    agency.set_account_active(db, identity.user_id, user_id, payload.is_active)


@router.get("/settings/operations")
def settings(db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": {"timezone": agency.operational(db, identity.user_id)}}


@router.patch("/settings/operations")
def update_settings(payload: Operational, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": {"timezone": agency.operational(db, identity.user_id, payload.timezone)}}
