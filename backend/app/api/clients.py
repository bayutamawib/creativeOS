from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import Database, Identity
from app.services import clients

router = APIRouter()


@router.get("/clients/{client_id}")
def profile(
    client_id: UUID,
    db: Database,
    identity: Identity,
    portal: Literal["client", "agency"] = "client",
) -> dict[str, Any]:
    return {"data": clients.profile(db, identity.user_id, client_id, portal=portal)}


@router.get("/clients/{client_id}/projects")
def projects(client_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": clients.projects(db, identity.user_id, client_id)}


@router.get("/projects/{project_id}/approval-authority")
def authority(project_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": clients.authority(db, identity.user_id, project_id)}


@router.get("/projects/{project_id}/approval-delegations")
def delegations(project_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": clients.grant_list(db, identity.user_id, project_id)}


@router.put("/projects/{project_id}/approval-delegations/{membership_id}", status_code=204)
def grant(project_id: UUID, membership_id: UUID, db: Database, identity: Identity) -> None:
    clients.change_grant(db, identity.user_id, project_id, membership_id, True)


@router.delete("/projects/{project_id}/approval-delegations/{membership_id}", status_code=204)
def revoke(project_id: UUID, membership_id: UUID, db: Database, identity: Identity) -> None:
    clients.change_grant(db, identity.user_id, project_id, membership_id, False)
