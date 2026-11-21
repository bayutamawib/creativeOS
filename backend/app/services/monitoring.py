from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import runner
from app.ai_models import Generation
from app.models import Project
from app.operations_models import DeliveryAttempt, Notification, Outbox, ProcessedEvent, WorkflowRun
from app.security import now
from app.services import agency, workflows

TRANSIENT = {"provider_unavailable", "provider_rate_limit", "worker_lease_expired"}


def duration(start: datetime | None, end: datetime | None) -> int | None:
    return max(0, round(((end or now()) - start).total_seconds() * 1000)) if start else None


def reconcile_expired(db: Session) -> None:
    instant = now()
    stale_schedules = db.scalars(
        select(WorkflowRun)
        .join(Outbox, Outbox.id == WorkflowRun.event_id)
        .where(
            WorkflowRun.status == "running",
            Outbox.event_type == "report.schedule",
            func.coalesce(WorkflowRun.last_callback_at, WorkflowRun.created_at)
            < instant - timedelta(minutes=10),
        )
        .limit(50)
        .with_for_update(of=WorkflowRun, skip_locked=True)
    )
    for run in stale_schedules:
        run.status = "failed"
        run.error_code = "schedule_callback_expired"
        run.completed_at = instant
    notices = db.scalars(
        select(Notification)
        .where(Notification.delivery_status == "sending", Notification.claim_expires_at <= now())
        .limit(50)
        .with_for_update(skip_locked=True)
    )
    for notice in notices:
        notice.delivery_status = "uncertain"
        notice.claim_expires_at = None
        attempt = db.scalar(
            select(DeliveryAttempt)
            .where(DeliveryAttempt.notification_id == notice.id)
            .order_by(DeliveryAttempt.attempt.desc())
            .limit(1)
        )
        if attempt and attempt.status == "sending":
            attempt.status = "uncertain"
            attempt.finished_at = now()
            attempt.error_code = "delivery_unconfirmed"


def failed_stage(db: Session, e: Outbox) -> Generation | None:
    if e.status != "delivered" or e.event_type not in {
        "brief.approved",
        "creative_direction.approved",
    }:
        return None
    run = db.scalar(
        select(WorkflowRun).where(WorkflowRun.event_id == e.id, WorkflowRun.attempt == e.attempts)
    )
    if not run or run.status != "failed" or run.error_code != "generation_failed":
        return None
    failures = db.scalars(
        select(Generation).where(
            Generation.event_id == e.id, Generation.status.in_(["failed", "cancelled"])
        )
    ).all()
    if len(failures) == 1:
        g = failures[0]
        if g.status == "failed" and g.error_code in TRANSIENT and runner.eligible(db, g):
            return g
    return None


def retryable_event(db: Session, e: Outbox) -> bool:
    recover_stage = e.status == "delivered" and failed_stage(db, e) is not None
    if not recover_stage and (
        e.status != "failed"
        or e.event_type not in workflows.ROUTES
        or e.error_code not in {"dispatch_unconfirmed", "dispatch_lease_expired"}
    ):
        return False
    # Only the atomic development adapter has a verified replay contract.
    unsafe = db.scalar(
        select(Notification.id)
        .where(
            Notification.event_id == e.id,
            (Notification.channel != "development-inbox")
            | Notification.delivery_status.in_(["uncertain", "sending"]),
        )
        .limit(1)
    )
    return unsafe is None


def event_view(db: Session, row: Outbox, *, completed_run: bool = False) -> dict[str, Any]:
    return dict(
        id=row.id,
        kind=row.event_type,
        resource_id=row.aggregate_id,
        status=row.status,
        attempt=row.attempts,
        created_at=row.created_at,
        finished_at=row.delivered_at or row.failed_at,
        duration_ms=duration(row.created_at, row.delivered_at or row.failed_at),
        error=row.error_code,
        retryable=False
        if row.status == "delivered" and completed_run
        else retryable_event(db, row),
    )


def run_view(row: WorkflowRun) -> dict[str, Any]:
    return dict(
        id=row.id,
        event_id=row.event_id,
        workflow=row.workflow_name,
        version=row.workflow_version,
        status=row.status,
        execution=row.n8n_execution_id,
        attempt=row.attempt,
        error=row.error_code,
        started_at=row.created_at,
        last_callback_at=row.last_callback_at,
        finished_at=row.completed_at,
        duration_ms=duration(row.created_at, row.completed_at),
    )


def job_retryable(db: Session, g: Generation) -> bool:
    return (
        g.status == "failed"
        and g.error_code in TRANSIENT
        and not g.report_id
        and not g.run_id
        and runner.eligible(db, g)
    )


def job_view(db: Session, g: Generation) -> dict[str, Any]:
    return dict(
        id=g.id,
        project_id=g.project_id,
        kind=g.generation_type,
        status=g.status,
        error=g.error_code,
        attempt=g.attempt,
        run_id=g.run_id,
        event_id=g.event_id,
        report_id=g.report_id,
        provider=g.provider,
        model=g.model,
        prompt_version=g.prompt_version,
        started_at=g.started_at,
        finished_at=g.completed_at,
        duration_ms=duration(g.started_at, g.completed_at),
        latency_ms=g.latency_ms,
        input_tokens=g.input_tokens,
        output_tokens=g.output_tokens,
        retryable=job_retryable(db, g),
    )


def detail(db: Session, event: Outbox) -> dict[str, Any]:
    receipts = db.scalars(
        select(ProcessedEvent)
        .where(ProcessedEvent.event_id == event.id)
        .order_by(ProcessedEvent.created_at)
    )
    attempts = db.execute(
        select(DeliveryAttempt, Notification)
        .join(Notification, Notification.id == DeliveryAttempt.notification_id)
        .where(Notification.event_id == event.id)
        .order_by(DeliveryAttempt.created_at)
    )
    return dict(
        event=event_view(db, event),
        runs=[
            run_view(r)
            for r in db.scalars(
                select(WorkflowRun)
                .where(WorkflowRun.event_id == event.id)
                .order_by(WorkflowRun.attempt.desc())
            )
        ],
        jobs=[
            job_view(db, g)
            for g in db.scalars(select(Generation).where(Generation.event_id == event.id))
        ],
        receipts=[
            dict(
                id=r.id,
                run_id=r.run_id,
                step=r.consumer_name,
                status=r.result_status,
                created_at=r.created_at,
            )
            for r in receipts
        ],
        deliveries=[
            dict(
                id=a.id,
                notification_id=n.id,
                recipient_id=n.recipient_id,
                run_id=a.run_id,
                channel=n.channel,
                attempt=a.attempt,
                status=a.status,
                finished_at=a.finished_at,
                error=a.error_code,
                duration_ms=duration(a.created_at, a.finished_at),
            )
            for a, n in attempts
        ],
    )


def retry_event(db: Session, actor: UUID, key: UUID, expected_run: UUID | None = None) -> None:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    e = db.get(Outbox, key, with_for_update=True)
    if not e:
        raise HTTPException(404, "Event unavailable")
    if expected_run:
        r = db.get_one(WorkflowRun, expected_run)
        if r.event_id != e.id or r.attempt != e.attempts or r.status != "failed":
            raise HTTPException(409, "Workflow attempt is no longer eligible")
    if not retryable_event(db, e):
        raise HTTPException(409, "Delivery requires reconciliation or is already settled")
    stage = failed_stage(db, e)
    if stage:
        db.get_one(Project, stage.project_id, with_for_update=True)
        db.refresh(stage, with_for_update=True)
        if not runner.eligible(db, stage):
            raise HTTPException(409, "Generation input changed")
        requeue_job(db, actor, stage)
    e.delivered_at = None
    e.retry_allowance = max(e.retry_allowance, e.attempts)
    e.status = "pending"
    e.failed_at = None
    e.error_code = None
    e.next_attempt_at = now()
    agency.audit(db, actor, "workflow.retry", e.id, {"previous_attempts": e.attempts})


def retry_job(db: Session, actor: UUID, key: UUID) -> None:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    project = db.scalar(select(Generation.project_id).where(Generation.id == key))
    if not project:
        raise HTTPException(404, "Job unavailable")
    db.get_one(Project, project, with_for_update=True)
    g = db.get_one(Generation, key, with_for_update=True)
    if not job_retryable(db, g):
        raise HTTPException(409, "Generation requires new inputs or its originating workflow")
    requeue_job(db, actor, g)


def requeue_job(db: Session, actor: UUID, g: Generation) -> None:
    g.retry_allowance = g.attempt
    g.status = "pending"
    g.completed_at = None
    g.next_attempt_at = now()
    g.error_code = None
    agency.audit(db, actor, "generation.retry", g.id, {"previous_attempts": g.attempt})
