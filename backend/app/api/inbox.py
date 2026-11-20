from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import String, and_, or_, select

from app.ai_models import ContentItem
from app.api.deps import Database, Identity
from app.brief_models import Snapshot
from app.models import ClientMembership, Project
from app.operations_models import Notification, Outbox, WorkflowRun
from app.project_inputs import Portal
from app.project_models import Task, TaskAssignee
from app.report_models import Report
from app.review_models import Review
from app.security import now
from app.services import agency, projects, reminders

router = APIRouter()


@router.get("/notifications")
def inbox(db: Database, identity: Identity, portal: Portal = "agency") -> dict[str, Any]:
    actor = identity.user_id
    roles = agency.roles(db, actor)
    if portal == "agency" and not roles:
        raise HTTPException(403, "Agency access required")
    current_assignment = (
        select(TaskAssignee.id)
        .join(Project, Project.id == TaskAssignee.project_id)
        .where(
            TaskAssignee.task_id == Outbox.aggregate_id,
            TaskAssignee.user_id == actor,
            Project.archived_at.is_(None),
            TaskAssignee.id.cast(String) == Outbox.payload["assignment_id"].astext,
        )
        .exists()
    )
    eligible = and_(Outbox.event_type == "task.assigned", current_assignment)
    if roles & {"admin", "agency_manager"}:
        eligible = or_(
            eligible,
            Outbox.event_type.in_(
                ["report.drafted", "lead.created", "brief.approved", "creative_direction.approved"]
            ),
        )
    if portal == "client":
        eligible = and_(
            Outbox.event_type == "content.client_review_requested",
            select(ContentItem.id)
            .join(Project, Project.id == ContentItem.project_id)
            .join(ClientMembership, ClientMembership.client_id == ContentItem.client_id)
            .join(Review, Review.revision_id == ContentItem.current_revision_id)
            .where(
                ContentItem.id == Outbox.aggregate_id,
                Project.archived_at.is_(None),
                ClientMembership.user_id == actor,
                ClientMembership.is_active,
                Review.stage == "client",
                Review.decision == "pending",
                Review.revision_id.cast(String) == Outbox.payload["revision_id"].astext,
            )
            .exists(),
        )
        eligible = or_(
            eligible,
            and_(
                Outbox.event_type == "report.published",
                select(Report.id)
                .where(
                    Report.id == Outbox.aggregate_id,
                    Report.status == "published",
                    Report.project_id.in_(
                        projects.scope(db, actor, "client").with_only_columns(Project.id)
                    ),
                )
                .exists(),
            ),
        )
    else:
        visible_decision = (
            select(ContentItem.id)
            .where(
                ContentItem.id == Outbox.aggregate_id,
                ContentItem.project_id.in_(
                    projects.scope(db, actor, "agency").with_only_columns(Project.id)
                ),
            )
            .exists()
        )
        due_assignment = (
            select(TaskAssignee.id)
            .join(Project, Project.id == TaskAssignee.project_id)
            .join(Task, Task.id == TaskAssignee.task_id)
            .where(
                Task.id == Outbox.aggregate_id,
                TaskAssignee.user_id == actor,
                Project.archived_at.is_(None),
                Task.status.notin_(["completed", "cancelled"]),
            )
            .exists()
        )
        eligible = or_(
            eligible,
            and_(
                Outbox.event_type.in_(["content.client_approved", "content.revision_requested"]),
                visible_decision,
            ),
            and_(
                Outbox.event_type == "task.deadline_reminder",
                Outbox.payload["window"].astext == str(reminders.day(now())),
                due_assignment,
            ),
        )
    rows = db.execute(
        select(Notification, Outbox, Snapshot.brief_id)
        .join(Outbox, Notification.event_id == Outbox.id)
        .outerjoin(Snapshot, Snapshot.id.cast(String) == Outbox.payload["snapshot_id"].astext)
        .where(
            Notification.recipient_id == actor,
            Notification.delivery_status == "delivered",
            eligible,
        )
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    return {
        "data": [
            {
                "id": notice.id,
                "message": notice.message,
                "channel": notice.channel,
                "delivered_at": notice.delivered_at,
                "resource_type": event.aggregate_type,
                "brief_id": brief_id,
                "resource_id": event.aggregate_id,
            }
            for notice, event, brief_id in rows
        ]
    }


@router.get("/automation/runs")
def monitoring(db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.execute(
        select(Outbox, WorkflowRun)
        .outerjoin(
            WorkflowRun,
            (WorkflowRun.event_id == Outbox.id) & (WorkflowRun.attempt == Outbox.attempts),
        )
        .order_by(Outbox.created_at.desc())
        .limit(100)
    )
    return {
        "data": [
            {
                "event_id": e.id,
                "event_type": e.event_type,
                "delivery": e.status,
                "attempt": e.attempts,
                "execution": r.n8n_execution_id if r else None,
                "status": r.status if r else None,
                "error": r.error_code if r else None,
            }
            for e, r in rows
        ]
    }
