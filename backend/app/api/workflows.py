import secrets
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field

from app.api.deps import Database
from app.config import settings
from app.schemas import Input
from app.services import workflows


def authenticate(x_creative_service: Annotated[str | None, Header()] = None) -> None:
    if not secrets.compare_digest(
        (x_creative_service or "").encode(), workflows.secret(settings().workflow_key).encode()
    ):
        raise HTTPException(403, "Workflow credential required")


router = APIRouter(prefix="/internal/workflow-runs", dependencies=[Depends(authenticate)])


class Trigger(Input):
    raw: str = Field(max_length=3000)
    timestamp: str = Field(max_length=12)
    signature: str = Field(pattern="^[0-9a-f]{64}$")
    execution_id: str = Field(pattern="^[0-9]{1,30}$")
    workflow: str = Field(max_length=20)


class Outcome(Input):
    status: Literal["completed"]


@router.post("")
def start(data: Trigger, db: Database) -> dict[str, UUID]:
    return {
        "run_id": workflows.start(
            db, data.raw, data.timestamp, data.signature, data.execution_id, data.workflow
        )
    }


@router.post("/{run_id}/notifications")
def notify(run_id: UUID, db: Database) -> dict[str, UUID]:
    workflows.deliver(db, run_id)
    return {"run_id": run_id}


@router.post("/{run_id}/outcome")
def outcome(run_id: UUID, data: Outcome, db: Database) -> dict[str, str]:
    return workflows.finish(db, run_id)
