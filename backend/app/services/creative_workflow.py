from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_models import Generation
from app.brief_models import Snapshot
from app.models import Project
from app.operations_models import Outbox, WorkflowRun
from app.security import now
from app.services import studio, workflows


def context(db: Session, run_id: UUID) -> tuple[WorkflowRun, Outbox, Snapshot]:
    run, event = workflows.run_context(db, run_id)
    if run.workflow_name != "WF-B" or event.event_type not in {
        "brief.approved",
        "creative_direction.approved",
    }:
        raise HTTPException(403, "Creative workflow required")
    if run.attempt != event.attempts:
        raise HTTPException(409, "Workflow attempt superseded")
    snap = db.get_one(Snapshot, UUID(event.payload["snapshot_id"]))
    return run, event, snap


def queue(db: Session, run_id: UUID, stage: str) -> dict[str, Any]:
    run, event, snap = context(db, run_id)
    db.get_one(Project, snap.project_id, with_for_update=True)
    allowed = {
        "brief.approved": {"brief_analysis", "creative_strategy"},
        "creative_direction.approved": {"content_plan"},
    }
    if stage not in allowed[event.event_type]:
        raise HTTPException(403, "Stage outside workflow scope")
    if not studio.current(db, snap):
        return {"run_id": run.id, "status": "cancelled"}
    opt = studio.Options(snapshot_id=snap.id, channels=None, target_count=None)
    if stage == "content_plan":
        opt.direction_proposal_id = event.aggregate_id
    elif event.aggregate_id != snap.brief_id:
        raise HTTPException(409, "Event resource mismatch")
    if run.status != "running":
        raise HTTPException(409, "Workflow attempt is closed")
    job = studio.enqueue(db, snap, stage, str(event.id) + "/" + stage, opt, run=run)
    return {"run_id": run.id, "generation_id": job.id, "status": job.status}


def poll(db: Session, run_id: UUID, key: UUID) -> dict[str, Any]:
    run, event, _ = context(db, run_id)
    job = db.get(Generation, key)
    if not job or job.event_id != event.id:
        raise HTTPException(404, "Workflow generation unavailable")
    return {"run_id": run.id, "generation_id": job.id, "status": job.status}


def final_state(db: Session, event: Outbox) -> str:
    snap = db.get_one(Snapshot, UUID(event.payload["snapshot_id"]))
    if not studio.current(db, snap):
        return "cancelled"
    jobs = list(db.scalars(select(Generation).where(Generation.event_id == event.id)))
    if any(j.status in {"failed", "cancelled"} for j in jobs):
        return "failed"
    required = (
        {"brief_analysis", "creative_strategy"}
        if event.event_type == "brief.approved"
        else {"content_plan"}
    )
    if required <= {j.generation_type for j in jobs if j.status == "completed"}:
        return "completed"
    return "running"


def outcome(db: Session, run_id: UUID) -> dict[str, str]:
    run, event, _ = context(db, run_id)
    if run.status in {"completed", "failed", "cancelled"}:
        return {"event_id": str(event.id), "run_id": str(run.id), "status": run.status}
    status = final_state(db, event)
    if status == "running":
        raise HTTPException(409, "Creative stages incomplete")
    if status == "completed":
        workflows.deliver(db, run.id)

    run.status, run.completed_at = status, now()
    if status != "completed":
        run.error_code = "ineligible_snapshot" if status == "cancelled" else "generation_failed"
    return {"event_id": str(event.id), "run_id": str(run.id), "status": status}
