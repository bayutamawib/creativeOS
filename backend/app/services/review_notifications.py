from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_models import ContentItem
from app.models import AgencyMembership, ClientMembership, Project, User
from app.operations_models import Outbox
from app.project_models import ProjectMember
from app.review_models import Review


def eligible(db: Session, event: Outbox) -> tuple[set[UUID], str]:
    item = db.get_one(ContentItem, event.aggregate_id)
    project = db.get_one(Project, item.project_id, with_for_update=True)
    db.refresh(item)
    revision = UUID(event.payload["revision_id"])
    row = db.scalar(
        select(Review).where(
            Review.content_item_id == item.id,
            Review.revision_id == revision,
            Review.stage == "client",
        )
    )
    if not row or project.archived_at:
        return set(), "Review unavailable."
    if event.event_type == "content.client_review_requested":
        if row.decision != "pending" or item.current_revision_id != revision:
            return set(), "Review closed."
        users = (
            select(ClientMembership.user_id)
            .join(User)
            .where(
                User.is_active,
                ClientMembership.client_id == item.client_id,
                ClientMembership.is_active,
            )
        )
        return set(
            db.scalars(users.with_for_update(read=True))
        ), f"{item.title} is ready for your review."
    expected = "approved" if event.event_type == "content.client_approved" else "revision_requested"
    if row.decision != expected:
        return set(), "Decision unavailable."
    users = (
        select(AgencyMembership.user_id)
        .join(User)
        .where(
            User.is_active,
            AgencyMembership.is_active,
            AgencyMembership.role.in_(["admin", "agency_manager"])
            | AgencyMembership.user_id.in_(
                select(ProjectMember.user_id).where(ProjectMember.project_id == item.project_id)
            ),
        )
    )
    return set(db.scalars(users)), f"{item.title} · client {expected.replace('_', ' ')}"
