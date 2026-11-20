from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.ai_models import ContentRevision
from app.api.deps import Database, Identity
from app.brief_inputs import Paragraph
from app.models import Project
from app.project_inputs import Portal
from app.schemas import Input
from app.services import projects, reviews

router = APIRouter()


class Decision(Input):
    revision_id: UUID
    comments: Paragraph | None = None
    decision: Literal["approved", "revision_requested"] | None = None


def register(action: str) -> None:
    def apply(
        content_id: UUID, data: Decision, db: Database, identity: Identity
    ) -> dict[str, bool]:
        if data.decision and data.decision != (
            "revision_requested"
            if action in {"request-internal-changes", "request-revision"}
            else "approved"
        ):
            raise HTTPException(422, "Decision conflicts with action")
        reviews.transition(
            db, identity.user_id, content_id, data.revision_id, action, data.comments
        )
        return {"data": True}

    router.add_api_route(
        "/content-items/{content_id}/" + action, apply, methods=["POST"], name=action
    )


for action in (
    "submit-for-internal-review",
    "approve-and-release",
    "request-internal-changes",
    "client-approval",
    "request-revision",
):
    register(action)


@router.get("/approvals")
def queue(db: Database, identity: Identity, portal: Portal) -> dict[str, Any]:
    return {"data": reviews.listing(db, identity.user_id, portal)}


class Comment(Input):
    revision_id: UUID
    message: Paragraph
    visibility: Literal["internal", "client_visible"]


@router.post("/content-items/{content_id}/feedback")
def comment(
    content_id: UUID, data: Comment, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, bool]:
    actor = identity.user_id
    mode = projects.effective_portal(db, actor, portal)
    item = reviews.item_for(db, actor, content_id, mode, True)
    rev = db.get(ContentRevision, data.revision_id)
    if not rev or rev.content_item_id != item.id:
        raise HTTPException(404, "Revision unavailable")
    if mode == "client" and (
        data.visibility != "client_visible" or not reviews.review(db, rev.id, "client")
    ):
        raise HTTPException(403, "Only released revisions accept client feedback")
    reviews.note(db, actor, item, rev.id, data.message, data.visibility)
    projects.change_log(db, actor, db.get_one(Project, item.project_id), "content.feedback", rev.id)
    return {"data": True}


@router.get("/content-items/{content_id}/feedback")
def feedback(
    content_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    mode = projects.effective_portal(db, identity.user_id, portal)
    item = reviews.item_for(db, identity.user_id, content_id, mode)
    return {"data": reviews.view(db, identity.user_id, item, mode)["feedback"]}
