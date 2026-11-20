from datetime import date, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AgencyMembership, Project, User
from app.operations_models import Outbox, WorkflowRun
from app.project_models import Task, TaskAssignee
from app.security import now


def day(at: datetime) -> date:
    return at.astimezone(ZoneInfo(settings().agency_timezone)).date()


def kind(due: date | None, window: date) -> str | None:
    if due is None or due > window + timedelta(days=1):
        return None
    if due == window:
        return "due_today"
    return "overdue" if due < window else "upcoming"


def scan(db: Session, execution: str, at: datetime) -> dict[str, str]:
    window = day(at)
    key = uuid5(NAMESPACE_URL, "creativeos:deadline-scan:" + str(window))
    db.execute(
        insert(Outbox)
        .values(
            id=key,
            event_type="deadline.scan",
            aggregate_type="schedule",
            aggregate_id=key,
            payload={"window": str(window)},
            status="delivered",
            delivered_at=at,
        )
        .on_conflict_do_nothing()
    )
    event = db.get_one(Outbox, key, with_for_update=True)
    run = db.scalar(
        select(WorkflowRun).where(
            WorkflowRun.event_id == key, WorkflowRun.n8n_execution_id == execution
        )
    )
    if run:
        return {"run_id": str(run.id), "status": run.status}
    event.attempts += 1
    run = WorkflowRun(
        event_id=key,
        attempt=event.attempts,
        workflow_name="WF-C",
        workflow_version="1.0",
        n8n_execution_id=execution,
        status="completed",
        completed_at=at,
    )
    db.add(run)
    db.flush()
    rows = db.execute(
        select(Task, TaskAssignee.user_id)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .join(Project, Project.id == Task.project_id)
        .join(User, User.id == TaskAssignee.user_id)
        .where(
            User.is_active,
            Project.archived_at.is_(None),
            Task.status.notin_(["completed", "cancelled"]),
            Task.due_date <= window + timedelta(days=1),
            User.id.in_(select(AgencyMembership.user_id).where(AgencyMembership.is_active)),
        )
    )
    for task, user in rows:
        reason = kind(task.due_date, window)
        dedup = f"creativeos:reminder:{task.id}:{user}:development-inbox:{window}:{reason}"
        db.execute(
            insert(Outbox)
            .values(
                id=uuid5(NAMESPACE_URL, dedup),
                aggregate_id=task.id,
                aggregate_type="task",
                event_type="task.deadline_reminder",
                payload={
                    "window": str(window),
                    "kind": reason,
                    "recipient": str(user),
                    "scan_run_id": str(run.id),
                },
            )
            .on_conflict_do_nothing()
        )
    return {"run_id": str(run.id), "status": run.status}


def recipients(db: Session, event: Outbox) -> tuple[set[UUID], str]:
    from app.services import agency

    user = UUID(event.payload["recipient"])
    task = db.get(Task, event.aggregate_id)
    if not task:
        return set(), "Task unavailable."
    project = db.get_one(Project, task.project_id, with_for_update=True)
    db.refresh(task)
    window = day(now())
    reason = event.payload["kind"]
    assigned = db.scalar(
        select(TaskAssignee.id).where(TaskAssignee.task_id == task.id, TaskAssignee.user_id == user)
    )
    if (
        project.archived_at
        or not assigned
        or not agency.roles(db, user)
        or task.status in {"completed", "cancelled"}
        or str(window) != event.payload["window"]
        or kind(task.due_date, window) != reason
    ):
        return set(), "Reminder no longer due."
    return {user}, f"{task.title} · {reason.replace('_', ' ')}"
