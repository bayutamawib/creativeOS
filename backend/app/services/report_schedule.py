from datetime import datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Project
from app.operations_models import Outbox, WorkflowRun
from app.report_models import Report, ScheduledReport
from app.security import now
from app.services import reminders, reports


def register(db: Session, execution: str, at: datetime) -> UUID:
    # A delayed callback can cross the weekly boundary. Resolve execution identity first.
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,6))"),
        {"key": "report.schedule/" + execution},
    )
    existing = db.scalar(
        select(WorkflowRun.id)
        .join(Outbox, Outbox.id == WorkflowRun.event_id)
        .where(Outbox.event_type == "report.schedule", WorkflowRun.n8n_execution_id == execution)
    )
    if existing:
        return existing
    today = reminders.day(at)
    start = today - timedelta(days=today.weekday() + 7)
    key = uuid5(NAMESPACE_URL, "creativeos:weekly-report:" + str(start))
    db.execute(
        insert(Outbox)
        .values(
            id=key,
            aggregate_type="schedule",
            aggregate_id=key,
            event_type="report.schedule",
            status="delivered",
            delivered_at=at,
            payload={"start": start.isoformat()},
        )
        .on_conflict_do_nothing()
    )
    event = db.get_one(Outbox, key, with_for_update=True)
    event.attempts += 1
    run = WorkflowRun(
        event_id=key,
        attempt=event.attempts,
        workflow_name="WF-D",
        workflow_version="1.0",
        n8n_execution_id=execution,
        last_callback_at=at,
    )
    db.add(run)
    db.flush()
    return run.id


def status(db: Session, key: UUID, *, enqueue: bool) -> dict[str, str]:
    from datetime import date

    run = db.get(WorkflowRun, key, with_for_update=True)
    if not run or run.workflow_name != "WF-D":
        raise HTTPException(404, "Schedule run unavailable")
    event = db.get_one(Outbox, run.event_id)
    if event.event_type != "report.schedule":
        raise HTTPException(409, "Weekly schedule required")
    if run.status == "running":
        run.last_callback_at = now()
        start = date.fromisoformat(event.payload["start"])
        if enqueue:
            projects = db.scalars(
                select(Project)
                .where(
                    Project.archived_at.is_(None),
                    Project.status.in_(["planning", "in_progress", "in_review"]),
                )
                .order_by(Project.id)
            ).all()
            for project in projects:
                row = reports.generate(
                    db, project, start, start + timedelta(days=6), "weekly", run=run
                )
                db.execute(
                    insert(ScheduledReport)
                    .values(run_id=key, report_id=row.id)
                    .on_conflict_do_nothing()
                )
        states = set(
            db.scalars(
                select(Report.status)
                .join(ScheduledReport, ScheduledReport.report_id == Report.id)
                .where(ScheduledReport.run_id == key)
            )
        )
        if "generating" not in states and (enqueue or states):
            run.status = "failed" if "failed" in states else "completed"
            run.error_code = "summary_failed" if run.status == "failed" else None
            run.completed_at = now()
    return {"run_id": str(key), "status": run.status}
