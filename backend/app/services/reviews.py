from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai_models import ContentItem, ContentRevision
from app.brief_models import FileAsset
from app.models import Project
from app.operations_models import Outbox
from app.project_inputs import Portal
from app.review_models import Feedback, Review, RevisionFile
from app.security import now
from app.services import agency, clients, projects, studio

PUBLIC_FIELDS = (
    "title",
    "headline",
    "caption",
    "draft_caption",
    "channel",
    "content_format",
    "visual_direction",
    "call_to_action",
    "hashtags",
)


def review(db: Session, revision: UUID, stage: str) -> Review | None:
    return db.scalar(select(Review).where(Review.revision_id == revision, Review.stage == stage))


def item_for(
    db: Session, actor: UUID, key: UUID, portal: Portal, write: bool = False
) -> ContentItem:
    if portal == "agency":
        return studio.item_context(db, actor, key, write)
    item = db.get(ContentItem, key)
    if not item:
        raise HTTPException(404, "Deliverable unavailable")
    clients.project_context(db, actor, item.project_id, lock=write)
    db.refresh(item)
    return item


def supersede(db: Session, item: ContentItem) -> None:
    db.execute(
        update(Review)
        .where(Review.content_item_id == item.id, Review.decision == "pending")
        .values(decision="superseded")
    )
    item.status = "draft"


def append(
    db: Session,
    actor: UUID,
    item: ContentItem,
    parent: UUID,
    headline: str,
    caption: str,
    attachment_ids: list[UUID] | None = None,
) -> None:
    if item.current_revision_id != parent:
        raise HTTPException(409, "Revision changed")
    old = db.get_one(ContentRevision, parent)
    data = dict(old.content)
    data.update(headline=headline, caption=caption)
    data.pop("draft_caption", None)
    supersede(db, item)
    rev = ContentRevision(
        content_item_id=item.id,
        revision_number=old.revision_number + 1,
        content=data,
        created_by=actor,
    )
    db.add(rev)
    db.flush()
    link_files(db, item, parent, rev.id, attachment_ids)
    item.current_revision_id = rev.id
    projects.change_log(
        db, actor, db.get_one(Project, item.project_id), "content.revision_saved", rev.id
    )


def note(
    db: Session, actor: UUID, item: ContentItem, rid: UUID, message: str, visibility: str
) -> None:
    db.add(
        Feedback(
            content_item_id=item.id,
            revision_id=rid,
            author_id=actor,
            message=message,
            visibility=visibility,
        )
    )


def transition(
    db: Session, actor: UUID, key: UUID, rid: UUID, action: str, comments: str | None
) -> None:
    client = action in {"client-approval", "request-revision"}
    item = item_for(db, actor, key, "client" if client else "agency", True)
    project = db.get_one(Project, item.project_id)
    stage = "client" if client else "internal"
    row = review(db, rid, stage)
    member_id = grant_id = None
    if client:
        if not row or row.content_item_id != key:
            raise HTTPException(404, "Release unavailable")
        member = clients.membership(db, actor, item.client_id, lock=True)
        grant = clients.active_grant(db, project, member)
        if member.role != "client_admin" and not grant:
            raise HTTPException(403, "Project approval authority required")
        member_id = member.id
        grant_id = grant.id if grant and member.role != "client_admin" else None
    elif action != "submit-for-internal-review":
        agency.manager_roles(db, actor)
    if item.current_revision_id != rid:
        raise HTTPException(409, "Revision changed")
    event = None
    if action == "submit-for-internal-review":
        if row or item.status != "draft":
            raise HTTPException(409, "Draft required")
        db.add(Review(content_item_id=key, revision_id=rid, stage=stage))
        item.status = "internal_review"
    else:
        if (
            not row
            or row.decision != "pending"
            or item.status != ("client_review" if client else "internal_review")
        ):
            raise HTTPException(409, "Review already resolved or unavailable")
        changes = action in {"request-revision", "request-internal-changes"}
        if changes and not comments:
            raise HTTPException(422, "Describe the requested changes")
        row.decision = "revision_requested" if changes else "approved"
        row.decided_at, row.decided_by, row.membership_id, row.delegation_id = (
            now(),
            actor,
            member_id,
            grant_id,
        )
        item.status = row.decision
        if comments:
            note(db, actor, item, rid, comments, "client_visible" if client else "internal")
        if action == "approve-and-release":
            db.add(Review(content_item_id=key, revision_id=rid, stage="client"))
            item.status = "client_review"
            event = "content.client_review_requested"
        elif client:
            event = "content.revision_requested" if changes else "content.client_approved"
    details = {"revision_id": str(rid), "action": action}
    projects.change_log(db, actor, project, "content." + action, key, details)
    if event:
        db.add(
            Outbox(
                event_type=event, aggregate_type="content_item", aggregate_id=key, payload=details
            )
        )


def revisions(db: Session, item: ContentItem, portal: Portal) -> list[ContentRevision]:
    stmt = select(ContentRevision).where(ContentRevision.content_item_id == item.id)
    if portal == "client":
        stmt = stmt.join(Review, Review.revision_id == ContentRevision.id).where(
            Review.stage == "client"
        )
    return list(db.scalars(stmt.order_by(ContentRevision.revision_number.desc())))


def view(db: Session, actor: UUID, item: ContentItem, portal: Portal) -> dict[str, Any]:
    history = revisions(db, item, portal)
    if not history:
        raise HTTPException(403, "No released content")
    current = history[0]
    stage = review(db, current.id, "client")
    allowed = []
    if portal == "agency":
        if item.status == "draft":
            allowed.append("submit-for-internal-review")
        if item.status == "internal_review" and agency.roles(db, actor) & {
            "admin",
            "agency_manager",
        }:
            allowed += ["approve-and-release", "request-internal-changes"]
    elif stage and stage.decision == "pending" and current.id == item.current_revision_id:
        project, member = clients.project_context(db, actor, item.project_id)
        if member.role == "client_admin" or clients.active_grant(db, project, member):
            allowed += ["client-approval", "request-revision"]
    notes = select(Feedback).where(Feedback.content_item_id == item.id)
    if portal == "client":
        notes = notes.where(
            Feedback.visibility == "client_visible",
            Feedback.revision_id.in_([r.id for r in history]),
        )
    return {
        "id": item.id,
        "title": item.title,
        "project_id": item.project_id,
        "available_files": [
            {"id": f.id, "name": f.file_name}
            for f in db.scalars(
                select(FileAsset).where(
                    FileAsset.project_id == item.project_id,
                    FileAsset.visibility == "internal",
                    FileAsset.archived_at.is_(None),
                )
            )
        ]
        if portal == "agency"
        else [],
        "revision_id": current.id,
        "revision_number": current.revision_number,
        "status": item.status if portal == "agency" else stage.decision if stage else None,
        "actions": allowed,
        "history": [
            {
                "id": r.id,
                "number": r.revision_number,
                "files": [{"id": f.id, "name": f.file_name} for f in attachments(db, r.id)],
                "content": r.content
                if portal == "agency"
                else {k: r.content[k] for k in PUBLIC_FIELDS if k in r.content},
            }
            for r in history
        ],
        "feedback": [
            {"revision_id": n.revision_id, "message": n.message, "visibility": n.visibility}
            for n in db.scalars(notes.order_by(Feedback.created_at))
        ],
    }


def listing(
    db: Session, actor: UUID, portal: Portal, project_id: UUID | None = None
) -> list[dict[str, Any]]:
    stmt = select(ContentItem).where(
        ContentItem.project_id.in_(projects.scope(db, actor, portal).with_only_columns(Project.id))
    )
    if project_id:
        stmt = stmt.where(ContentItem.project_id == project_id)
    if portal == "client":
        stmt = stmt.where(
            ContentItem.id.in_(select(Review.content_item_id).where(Review.stage == "client"))
        )
    return [
        view(db, actor, item, portal)
        for item in db.scalars(stmt.order_by(ContentItem.created_at.desc()))
    ]


def attachments(db: Session, rid: UUID) -> list[FileAsset]:
    return list(
        db.scalars(
            select(FileAsset)
            .join(RevisionFile, RevisionFile.file_id == FileAsset.id)
            .where(RevisionFile.revision_id == rid)
        )
    )


def link_files(
    db: Session, item: ContentItem, parent: UUID, rid: UUID, ids: list[UUID] | None = None
) -> None:
    keys = set(ids) if ids is not None else {f.id for f in attachments(db, parent)}
    allowed = set(
        db.scalars(
            select(FileAsset.id).where(
                FileAsset.id.in_(keys),
                FileAsset.project_id == item.project_id,
                FileAsset.archived_at.is_(None),
                FileAsset.visibility == "internal",
            )
        )
    )
    if keys != allowed:
        raise HTTPException(422, "Choose private files from this project")
    db.add_all([RevisionFile(file_id=f, revision_id=rid) for f in keys])
