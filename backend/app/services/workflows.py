"""Signed triggers, leased dispatch and idempotent local delivery."""

import hmac
import json
import time
from datetime import timedelta
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine
from app.models import AgencyMembership, Project, User
from app.operations_models import Lead, Notification, Outbox, ProcessedEvent, WorkflowRun
from app.project_models import Task, TaskAssignee
from app.security import now
from app.services import agency

ROUTES = {
    "brief.approved": ("WF-B", "creative-brief-approved"),
    "creative_direction.approved": ("WF-B", "creative-direction-approved"),
    "lead.created": ("WF-A", "creative-lead-created"),
    "task.assigned": ("WF-C", "creative-task-assigned"),
}
MAX_ATTEMPTS = 8


def secret(value: SecretStr | None) -> str:
    if not value or not value.get_secret_value():
        raise HTTPException(503, "Integration credential unavailable")
    return value.get_secret_value()


def signature(message: str) -> str:
    return hmac.new(secret(settings().webhook_key).encode(), message.encode(), "sha256").hexdigest()


def envelope(event: Outbox) -> str:
    return json.dumps(
        {
            "event_id": str(event.id),
            "event_type": event.event_type,
            "resource": {"type": event.aggregate_type, "id": str(event.aggregate_id)},
            "occurred_at": event.created_at.isoformat(),
            "workflow_version": "1.0",
            "attempt": event.attempts,
        },
        separators=(",", ":"),
    )


def start(db: Session, raw: str, timestamp: str, mac: str, execution: str, workflow: str) -> UUID:
    if (
        not timestamp.isascii()
        or not timestamp.isdigit()
        or abs(time.time() - int(timestamp)) > 120
        or not hmac.compare_digest(signature(timestamp + "." + raw), mac)
    ):
        raise HTTPException(403, "Invalid event signature")
    try:
        event_id = UUID(json.loads(raw)["event_id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, "Invalid envelope") from exc
    event = db.get(Outbox, event_id, with_for_update=True)
    if (
        not event
        or raw != envelope(event)
        or ROUTES.get(event.event_type, (None, None))[0] != workflow
    ):
        raise HTTPException(409, "Event does not match stored trigger")
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.event_id == event.id, WorkflowRun.attempt == event.attempts
        )
    )
    if not run:
        run = WorkflowRun(
            event_id=event.id,
            attempt=event.attempts,
            workflow_name=workflow,
            workflow_version="1.0",
            n8n_execution_id=execution,
        )
        db.add(run)
        db.flush()
    return run.id


def run_context(db: Session, run_id: UUID) -> tuple[WorkflowRun, Outbox]:
    event_id = db.scalar(select(WorkflowRun.event_id).where(WorkflowRun.id == run_id))
    if not event_id:
        raise HTTPException(404, "Run not found")
    event = db.get_one(Outbox, event_id, with_for_update=True)
    return db.get_one(WorkflowRun, run_id, with_for_update=True), event


def eligible(db: Session, event: Outbox) -> tuple[set[UUID], str]:
    if event.event_type == "lead.created" and db.get(Lead, event.aggregate_id) is not None:
        ids = db.scalars(
            select(AgencyMembership.user_id)
            .join(User)
            .where(
                User.is_active,
                AgencyMembership.is_active,
                AgencyMembership.role.in_(["admin", "agency_manager"]),
            )
        )
        return set(ids), "A new inquiry is ready for agency review."
    if event.event_type in {"brief.approved", "creative_direction.approved"}:
        from app.services.creative_workflow import final_state

        if final_state(db, event) != "completed":
            raise HTTPException(409, "Creative workflow is incomplete")
        ids = db.scalars(
            select(AgencyMembership.user_id)
            .join(User)
            .where(
                User.is_active,
                AgencyMembership.is_active,
                AgencyMembership.role.in_(["admin", "agency_manager"]),
            )
        )
        return set(ids), "Creative proposals are ready for agency review."
    if event.event_type == "task.assigned":
        assignment = db.get(TaskAssignee, UUID(event.payload["assignment_id"]))
        recipients: set[UUID] = set()
        if assignment and assignment.task_id == event.aggregate_id:
            project = db.get_one(Project, assignment.project_id, with_for_update=True)
            task = db.get_one(Task, assignment.task_id)
            if (
                not project.archived_at
                and task.status not in {"completed", "cancelled"}
                and agency.roles(db, assignment.user_id)
            ):
                recipients.add(assignment.user_id)
        return recipients, "A project task has been assigned to you."
    raise HTTPException(409, "Notification trigger unavailable")


def deliver(db: Session, run_id: UUID) -> None:
    run, event = run_context(db, run_id)
    if settings().app_env != "development":
        raise HTTPException(503, "Development notification adapter disabled")
    step = "development-inbox"
    receipt = db.scalar(
        select(ProcessedEvent).where(
            ProcessedEvent.event_id == event.id, ProcessedEvent.consumer_name == step
        )
    )
    if receipt:
        return
    agency.guard(db)
    recipients, message = eligible(db, event)
    for target in recipients:
        db.execute(
            insert(Notification)
            .values(
                recipient_id=target,
                event_id=event.id,
                channel=step,
                deduplication_key=str(event.id),
                message=message,
                delivery_status="delivered",
                delivered_at=now(),
            )
            .on_conflict_do_nothing(index_elements=["recipient_id", "channel", "deduplication_key"])
        )
    db.add(
        ProcessedEvent(
            event_id=event.id, consumer_name=step, result_status="completed", run_id=run.id
        )
    )


def finish(db: Session, run_id: UUID) -> dict[str, str]:
    run, event = run_context(db, run_id)
    if not db.scalar(
        select(ProcessedEvent.id).where(
            ProcessedEvent.event_id == event.id, ProcessedEvent.consumer_name == "development-inbox"
        )
    ):
        raise HTTPException(409, "Notification step incomplete")
    if run.status != "completed":
        run.status = "completed"
        run.completed_at = now()
    return {"event_id": str(event.id), "run_id": str(run.id), "status": "completed"}


def claim(db: Session) -> tuple[UUID, UUID, str, str] | None:
    current = now()
    row = db.scalar(
        select(Outbox)
        .where(
            Outbox.event_type.in_(ROUTES),
            or_(
                and_(Outbox.status == "pending", Outbox.next_attempt_at <= current),
                and_(Outbox.status == "processing", Outbox.claim_expires_at <= current),
            ),
        )
        .order_by(Outbox.next_attempt_at, Outbox.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if not row:
        return None
    if row.status == "processing":
        previous = db.scalar(
            select(WorkflowRun).where(
                WorkflowRun.event_id == row.id, WorkflowRun.attempt == row.attempts
            )
        )
        if previous and previous.status == "running":
            previous.status = "failed"
            previous.error_code = "dispatch_lease_expired"
            previous.completed_at = current
    if row.attempts >= MAX_ATTEMPTS:
        row.status = "failed"
        row.claim_token = row.claim_expires_at = None
        return None
    row.status = "processing"
    row.claim_token = uuid4()
    row.claim_expires_at = current + timedelta(seconds=60)
    row.attempts += 1
    return row.id, row.claim_token, ROUTES[row.event_type][1], envelope(row)


def settle(db: Session, event_id: UUID, token: UUID, ack: dict[str, Any] | None) -> None:
    event = db.get_one(Outbox, event_id, with_for_update=True)
    if event.claim_token != token:
        return
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.event_id == event_id, WorkflowRun.attempt == event.attempts
        )
    )
    if (
        run
        and (
            run.status == "completed"
            or run.workflow_name == "WF-B"
            and run.status in {"failed", "cancelled"}
        )
        and ack
        and ack.get("event_id") == str(event_id)
        and ack.get("run_id") == str(run.id)
        and ack.get("status") == run.status
    ):
        event.status = "delivered"
        event.delivered_at = now()
    else:
        event.status = "failed" if event.attempts >= MAX_ATTEMPTS else "pending"
        event.next_attempt_at = now() + timedelta(seconds=min(300, 2**event.attempts))
        if run and run.status != "completed":
            run.status = "failed"
            run.error_code = "dispatch_unconfirmed"
            run.completed_at = now()
    event.claim_token = event.claim_expires_at = None


def dispatch() -> bool:
    with Session(engine()) as db, db.begin():
        job = claim(db)
    if not job:
        return False
    event_id, token, path, body = job
    timestamp = str(int(time.time()))
    request = Request(
        settings().n8n_base_url + "/webhook/" + path,
        data=body.encode(),
        headers={
            "Content-Type": "application/json",
            "X-Creative-Timestamp": timestamp,
            "X-Creative-Signature": signature(timestamp + "." + body),
            "Authorization": "Bearer "
            + jwt.encode(
                {
                    "sub": "creative-dispatcher",
                    "iat": int(timestamp),
                    "exp": int(timestamp) + 30,
                    "jti": str(token),
                },
                signature("webhook-jwt-v1"),
                algorithm="HS256",
            ),
        },
        method="POST",
    )
    ack = None
    try:
        with urlopen(
            request,
            timeout=45
            if path in {"creative-brief-approved", "creative-direction-approved"}
            else 12,
        ) as response:
            result = json.load(response)
            if isinstance(result, dict):
                ack = result
    except (URLError, OSError, ValueError):
        pass
    with Session(engine()) as db, db.begin():
        settle(db, event_id, token, ack)
    return True
