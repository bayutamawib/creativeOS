from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import Database, Identity
from app.services import dashboard

router = APIRouter()


@router.get("/dashboard/agency")
def agency_dashboard(db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": dashboard.agency(db, identity.user_id)}


@router.get("/dashboard/client")
def client_dashboard(client_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": dashboard.client(db, identity.user_id, client_id)}
