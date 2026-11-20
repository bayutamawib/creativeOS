import secrets
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import Field

from app.api.deps import Database
from app.config import settings
from app.schemas import Input
from app.security import now
from app.services import creative_workflow, reminders, report_schedule, workflows


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
    status: Literal["completed", "failed", "cancelled"]


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
    run, event = workflows.run_context(db, run_id)
    if event.event_type in {"brief.approved", "creative_direction.approved"}:
        return creative_workflow.outcome(db, run_id)
    if data.status != "completed":
        raise HTTPException(409, "Notification step incomplete")
    return workflows.finish(db, run_id)


class Stage(Input):
    stage: Literal["brief_analysis", "creative_strategy", "content_plan"]


@router.post("/{run_id}/generations")
def enqueue_stage(run_id: UUID, data: Stage, db: Database) -> dict[str, Any]:
    return creative_workflow.queue(db, run_id, data.stage)


@router.get("/{run_id}/generations/{generation_id}")
def poll_stage(run_id: UUID, generation_id: UUID, db: Database) -> dict[str, Any]:
    return creative_workflow.poll(db, run_id, generation_id)


class Tick(Input):
    execution_id: str = Field(pattern="^[0-9]{1,30}$")


@router.post("/deadline-scan")
def deadline_scan(data: Tick, db: Database) -> dict[str, str]:
    return reminders.scan(db, data.execution_id, now())


@router.post("/report-schedule")
def reporting_tick(data: Tick, db: Database) -> dict[str, UUID]:
    return {"run_id": report_schedule.register(db, data.execution_id, now())}


@router.post("/{run_id}/reports")
def schedule_reports(run_id: UUID, db: Database) -> dict[str, str]:
    return report_schedule.status(db, run_id, enqueue=True)


@router.get("/{run_id}/reports")
def poll_reports(run_id: UUID, db: Database) -> dict[str, str]:
    return report_schedule.status(db, run_id, enqueue=False)
