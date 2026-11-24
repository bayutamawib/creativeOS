import json
from datetime import date, datetime, time, timedelta
from hashlib import sha256
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from app.ai.contracts import REPORT_PROMPT_VERSION, TEMPERATURES
from app.ai.reporting import instructions
from app.ai_models import Generation
from app.config import settings
from app.models import AgencyMembership, ClientMembership, Project, User
from app.operations_models import Outbox, WorkflowRun
from app.project_inputs import Portal
from app.report_models import Report
from app.security import now
from app.services import agency, projects

# All aggregates share one PostgreSQL statement snapshot. Only released milestones enter client progress.
METRICS = text("""
SELECT t.*, m.*, a.* FROM (
 SELECT count(*) AS total_tasks, count(*) FILTER (WHERE completed_at >= :lo AND completed_at < :hi) AS completed_tasks,
 count(*) FILTER (WHERE status NOT IN ('completed','cancelled')) AS open_tasks,
 count(*) FILTER (WHERE status='in_progress') AS in_progress_tasks,
 count(*) FILTER (WHERE status NOT IN ('completed','cancelled') AND due_date < :today) AS overdue_tasks,
 count(*) FILTER (WHERE due_date BETWEEN :start AND :end) AS deadlines_in_period
 FROM tasks WHERE project_id=:pid
) t CROSS JOIN (
 SELECT count(*) AS visible_milestones, count(*) FILTER (WHERE status='completed') AS completed_visible_milestones,
 count(*) FILTER (WHERE completed_at >= :lo AND completed_at < :hi) AS milestones_completed_in_period
 FROM milestones WHERE project_id=:pid AND client_visible
) m CROSS JOIN (
 SELECT count(*) FILTER (WHERE decision='pending') AS awaiting_client_approval,
 count(*) FILTER (WHERE decision='approved' AND decided_at>=:lo AND decided_at<:hi) AS approvals_in_period,
 count(*) FILTER (WHERE decision='revision_requested' AND decided_at>=:lo AND decided_at<:hi) AS revisions_requested_in_period
 FROM content_approvals JOIN content_items ON content_items.id=content_item_id
 WHERE project_id=:pid AND stage='client'
) a
""")


def bounds(start: date, end: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    if end < start or end == date.max:
        raise HTTPException(422, "Invalid report period")
    return datetime.combine(start, time.min, zone), datetime.combine(
        end + timedelta(days=1), time.min, zone
    )


def generate(
    db: Session,
    project: Project,
    start: date,
    end: date,
    kind: str,
    *,
    actor: UUID | None = None,
    run: WorkflowRun | None = None,
) -> Report:
    if (actor is None) == (run is None):
        raise ValueError("One requester is required")
    agency.guard_operational_write(db)
    if actor:
        agency.manager_roles(db, actor)
    project = db.get_one(Project, project.id, with_for_update=True, populate_existing=True)
    if project.archived_at:
        raise HTTPException(404, "Project unavailable")
    zone = ZoneInfo(settings().agency_timezone)
    lo, hi = bounds(start, end, zone)
    if kind == "weekly" and (start.weekday() != 0 or (end - start).days != 6):
        raise HTTPException(422, "Weekly reports cover Monday through Sunday")
    row = db.scalar(
        select(Report)
        .where(
            Report.project_id == project.id,
            Report.report_type == kind,
            Report.period_start == start,
            Report.period_end == end,
        )
        .with_for_update()
    )
    if row and row.status != "failed":
        return row
    if not row:
        at = now()
        counts = dict(
            db.execute(
                METRICS,
                dict(
                    pid=project.id,
                    lo=lo,
                    hi=hi,
                    today=at.astimezone(zone).date(),
                    start=start,
                    end=end,
                ),
            )
            .mappings()
            .one()
        )
        counts["progress_percent"] = projects.progress_counts(
            counts["visible_milestones"], counts["completed_visible_milestones"]
        )["percent"]
        metrics = dict(period=f"{start} to {end}", project_status=project.status, **counts)
        row = Report(
            project_id=project.id,
            client_id=project.client_id,
            report_type=kind,
            period_start=start,
            period_end=end,
            status="generating",
            metrics=metrics,
            provenance=dict(
                definition="project-period-v1",
                timezone=zone.key,
                captured_at=at.isoformat(),
                start_inclusive=lo.isoformat(),
                end_exclusive=hi.isoformat(),
                source_tables=[
                    "tasks",
                    "milestones",
                    "content_approvals",
                    "content_items",
                    "projects",
                ],
            ),
            requested_by=actor,
            service_identity=None if actor else "n8n:WF-D",
        )
        db.add(row)
        db.flush()
    else:
        row.version += 1
        row.status = "generating"
    cfg = settings()
    scope = str(actor) if actor else "n8n:WF-D"
    db.add(
        Generation(
            project_id=project.id,
            client_id=project.client_id,
            report_id=row.id,
            generation_type="report_summary",
            requester_scope=scope,
            requested_by=actor,
            service_identity=None if actor else scope,
            event_id=run.event_id if run else None,
            run_id=run.id if run else None,
            idempotency_key=f"{row.id}:{row.version}",
            fingerprint=sha256(json.dumps(row.metrics, sort_keys=True).encode()).hexdigest(),
            input_snapshot=row.metrics,
            parameters={
                "temperature": TEMPERATURES["report_summary"],
                "max_output_tokens": cfg.ai_max_output_tokens,
                **instructions(row.metrics),
            },
            provider=cfg.ai_provider,
            model=cfg.ai_model,
            prompt_version=REPORT_PROMPT_VERSION,
        )
    )
    if actor:
        projects.change_log(db, actor, project, "report.generation_requested", row.id)
    return row


def scoped(db: Session, actor: UUID, portal: Portal) -> Select[Report]:
    stmt = select(Report).where(
        Report.project_id.in_(projects.scope(db, actor, portal).with_only_columns(Project.id))
    )
    return stmt.where(Report.status == "published") if portal == "client" else stmt


def get(db: Session, actor: UUID, key: UUID, portal: Portal) -> Report:
    row = db.scalar(scoped(db, actor, portal).where(Report.id == key))
    if not row:
        raise HTTPException(404, "Report not found")
    return row


def view(row: Report) -> dict[str, Any]:
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "project_id",
            "report_type",
            "period_start",
            "period_end",
            "status",
            "version",
            "metrics",
            "provenance",
            "narrative",
            "published_at",
        )
    }


def transition(
    db: Session, actor: UUID, key: UUID, version: int, action: str, narrative: str | None = None
) -> Report:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    row = get(db, actor, key, "agency")
    project = projects.access(db, actor, row.project_id, write=True)
    db.refresh(row, with_for_update=True)
    allowed = {
        "edit": {"draft", "ready_for_review"},
        "submit": {"draft"},
        "publish": {"ready_for_review"},
    }
    if row.version != version or row.status not in allowed[action]:
        raise HTTPException(409, "Report version or review state changed")
    if action == "edit":
        row.status = "draft"
        row.narrative = narrative
    elif action == "submit":
        row.status = "ready_for_review"
    else:
        row.status = "published"
        row.published_at = now()
        row.published_by = actor
        db.add(
            Outbox(
                event_type="report.published",
                aggregate_type="report",
                aggregate_id=row.id,
                payload={},
            )
        )
    row.version += 1
    projects.change_log(db, actor, project, "report." + action, row.id, {"version": row.version})
    return row


def recipients(db: Session, event: Outbox) -> tuple[set[UUID], str]:
    row = db.get_one(Report, event.aggregate_id)
    if db.get_one(Project, row.project_id).archived_at:
        return set(), "Report unavailable."
    if event.event_type == "report.drafted":
        stmt = (
            select(AgencyMembership.user_id)
            .join(User)
            .where(
                User.is_active,
                AgencyMembership.is_active,
                AgencyMembership.role.in_(["admin", "agency_manager"]),
            )
        )
        return set(db.scalars(stmt)), "A project report is ready for agency review."
    if row.status != "published":
        return set(), "Report unavailable."
    stmt = (
        select(ClientMembership.user_id)
        .join(User)
        .where(
            User.is_active, ClientMembership.is_active, ClientMembership.client_id == row.client_id
        )
    )
    return set(
        db.scalars(stmt)
    ), f"Project report published for {row.period_start} to {row.period_end}."
