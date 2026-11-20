from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.ai_models import Generation
from app.api.deps import Database, Identity
from app.api.projects import Page, PageSize
from app.operations_models import DeliveryAttempt, Notification, Outbox, WorkflowRun
from app.services import agency
from app.services import monitoring as monitor

router = APIRouter(prefix="/admin")
Issue = Literal["failed", "uncertain"]


@router.get("/outbox")
def events(
    db: Database,
    identity: Identity,
    page: Page = 1,
    page_size: PageSize = 30,
    state: Issue | None = None,
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.scalars(
        select(Outbox)
        .where(*([Outbox.status == state] if state else []))
        .order_by(Outbox.created_at.desc(), Outbox.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": [monitor.event_view(db, e) for e in rows]}


@router.get("/workflow-runs")
def runs(
    db: Database,
    identity: Identity,
    page: Page = 1,
    page_size: PageSize = 30,
    state: Issue | None = None,
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.scalars(
        select(WorkflowRun)
        .where(*([WorkflowRun.status == state] if state else []))
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": [monitor.run_view(r) for r in rows]}


@router.get("/generation-jobs")
def jobs(
    db: Database,
    identity: Identity,
    page: Page = 1,
    page_size: PageSize = 30,
    state: Issue | None = None,
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.scalars(
        select(Generation)
        .where(*([Generation.status == state] if state else []))
        .order_by(Generation.created_at.desc(), Generation.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {"data": [monitor.job_view(db, g) for g in rows]}


@router.get("/outbox/{key}")
def details(key: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    e = db.get(Outbox, key)
    if not e:
        raise HTTPException(404, "Event unavailable")
    return {"data": monitor.detail(db, e)}


@router.get("/workflow-runs/{run_id}")
def run_detail(run_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    r = db.get(WorkflowRun, run_id)
    if not r:
        raise HTTPException(404, "Run unavailable")
    return {"data": monitor.detail(db, db.get_one(Outbox, r.event_id)) | {"selected_run_id": r.id}}


@router.post("/workflow-runs/{run_id}/retry")
def retry(run_id: UUID, db: Database, identity: Identity) -> dict[str, bool]:
    agency.manager_roles(db, identity.user_id)
    r = db.get(WorkflowRun, run_id)
    if not r:
        raise HTTPException(404, "Run unavailable")
    monitor.retry_event(db, identity.user_id, r.event_id, r.id)
    return {"data": True}


@router.post("/outbox/{key}/retry")
def retry_event(key: UUID, db: Database, identity: Identity) -> dict[str, bool]:
    monitor.retry_event(db, identity.user_id, key)
    return {"data": True}


@router.post("/generation-jobs/{key}/retry")
def retry_generation(key: UUID, db: Database, identity: Identity) -> dict[str, bool]:
    monitor.retry_job(db, identity.user_id, key)
    return {"data": True}


@router.get("/delivery-attempts")
def deliveries(
    db: Database,
    identity: Identity,
    page: Page = 1,
    page_size: PageSize = 30,
    state: Issue | None = None,
) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.execute(
        select(DeliveryAttempt, Notification.event_id, Notification.channel)
        .join(Notification, Notification.id == DeliveryAttempt.notification_id)
        .where(*([DeliveryAttempt.status == state] if state else []))
        .order_by(DeliveryAttempt.created_at.desc(), DeliveryAttempt.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return {
        "data": [
            dict(
                id=a.id,
                event_id=e,
                run_id=a.run_id,
                channel=channel,
                status=a.status,
                attempt=a.attempt,
                error=a.error_code,
                started_at=a.created_at,
                finished_at=a.finished_at,
                duration_ms=monitor.duration(a.created_at, a.finished_at),
            )
            for a, e, channel in rows
        ]
    }
