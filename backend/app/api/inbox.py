from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import String, and_, or_, select

from app.api.deps import Database, Identity
from app.brief_models import Snapshot
from app.models import Project
from app.operations_models import Notification, Outbox
from app.project_models import TaskAssignee
from app.services import agency

router = APIRouter()


@router.get("/notifications")
def inbox(db: Database, identity: Identity) -> dict[str, Any]:
    actor = identity.user_id
    roles = agency.roles(db, actor)
    if not roles:
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
                ["lead.created", "brief.approved", "creative_direction.approved"]
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
