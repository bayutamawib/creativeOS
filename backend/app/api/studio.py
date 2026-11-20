from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header
from pydantic import Field
from sqlalchemy import select

from app.ai_models import ContentItem, ContentRevision, Generation, Proposal
from app.api.deps import Database, Identity
from app.brief_inputs import Paragraph, Short
from app.brief_models import Snapshot
from app.config import settings
from app.operations_models import Outbox, WorkflowRun
from app.project_inputs import Portal
from app.schemas import Input
from app.services import briefs, projects, reviews, studio

router = APIRouter()
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=120)]


def generation_route(path: str, kind: str) -> None:
    def submit(
        brief_id: UUID, data: studio.Options, key: Key, db: Database, identity: Identity
    ) -> dict[str, Any]:
        job = studio.manual(db, identity.user_id, brief_id, kind, key, data)
        return {"data": {"generation_id": job.id, "status": job.status}}

    router.add_api_route(
        "/briefs/{brief_id}/" + path, submit, methods=["POST"], status_code=202, name=kind
    )


for path, kind in [
    ("analyze", "brief_analysis"),
    ("generate-creative-direction", "creative_strategy"),
    ("generate-content-plan", "content_plan"),
]:
    generation_route(path, kind)


@router.get("/ai-generations/{generation_id}")
def job(generation_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": studio.job_view(studio.scoped_job(db, identity.user_id, generation_id))}


@router.get("/projects/{project_id}/ai-generations")
def history(
    project_id: UUID, db: Database, identity: Identity, brief_id: UUID | None = None
) -> dict[str, Any]:
    projects.access(db, identity.user_id, project_id)
    stmt = select(Generation).where(Generation.project_id == project_id)
    if brief_id:
        stmt = stmt.join(Snapshot, Snapshot.id == Generation.snapshot_id).where(
            Snapshot.brief_id == brief_id
        )
    return {
        "data": [
            studio.job_view(j)
            for j in db.scalars(stmt.order_by(Generation.created_at.desc()).limit(100))
        ]
    }


@router.get("/briefs/{brief_id}/proposals")
def proposals(brief_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    briefs.get(db, identity.user_id, brief_id, "agency")
    rows = db.scalars(
        select(Proposal)
        .join(Snapshot, Snapshot.id == Proposal.snapshot_id)
        .where(Snapshot.brief_id == brief_id)
        .order_by(Proposal.created_at.desc(), Proposal.item_index)
    )
    return {"data": [studio.proposal_view(p) for p in rows]}


@router.post("/proposals/{proposal_id}/approve")
def approve(proposal_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": studio.proposal_view(studio.decide(db, identity.user_id, proposal_id, "approved"))
    }


@router.post("/proposals/{proposal_id}/reject")
def reject(proposal_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    return {
        "data": studio.proposal_view(studio.decide(db, identity.user_id, proposal_id, "rejected"))
    }


class FromProposal(Input):
    proposal_id: UUID


class Edit(Input):
    attachment_ids: list[UUID] | None = Field(None, max_length=20)
    revision_id: UUID
    headline: Short
    caption: Paragraph


class FromGeneration(Input):
    generation_id: UUID


@router.post("/projects/{project_id}/content-items", status_code=201)
def create_draft(
    project_id: UUID, data: FromProposal, db: Database, identity: Identity
) -> dict[str, Any]:
    return {
        "data": studio.item_view(
            db, studio.draft(db, identity.user_id, project_id, data.proposal_id)
        )
    }


@router.get("/projects/{project_id}/content-items")
def drafts(
    project_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    if projects.effective_portal(db, identity.user_id, portal) == "client":
        projects.access(db, identity.user_id, project_id, "client")
        return {"data": reviews.listing(db, identity.user_id, "client", project_id)}
    projects.access(db, identity.user_id, project_id)
    return {
        "data": [
            studio.item_view(db, i)
            for i in db.scalars(
                select(ContentItem)
                .where(ContentItem.project_id == project_id)
                .order_by(ContentItem.created_at.desc())
            )
        ]
    }


@router.get("/content-items/{content_id}")
def draft(
    content_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    if projects.effective_portal(db, identity.user_id, portal) == "client":
        return {
            "data": reviews.view(
                db,
                identity.user_id,
                reviews.item_for(db, identity.user_id, content_id, "client"),
                "client",
            )
        }
    return {"data": studio.item_view(db, studio.item_context(db, identity.user_id, content_id))}


@router.post("/content-items/{content_id}/generate", status_code=202)
def copywriting(
    content_id: UUID, data: studio.Options, key: Key, db: Database, identity: Identity
) -> dict[str, Any]:
    item = studio.item_context(db, identity.user_id, content_id, True)
    job = studio.manual(db, identity.user_id, item.brief_id, "copywriting", key, data, item)
    return {"data": {"generation_id": job.id, "status": job.status}}


@router.post("/content-items/{content_id}/revisions", status_code=201)
def save_suggestion(
    content_id: UUID, data: FromGeneration | Edit, db: Database, identity: Identity
) -> dict[str, Any]:
    if isinstance(data, Edit):
        item = studio.item_context(db, identity.user_id, content_id, True)
        reviews.append(
            db,
            identity.user_id,
            item,
            data.revision_id,
            data.headline,
            data.caption,
            data.attachment_ids,
        )
        return {"data": studio.item_view(db, item)}
    return {
        "data": studio.item_view(
            db, studio.save_copy(db, identity.user_id, content_id, data.generation_id)
        )
    }


@router.get("/content-items/{content_id}/revisions")
def revisions(
    content_id: UUID, db: Database, identity: Identity, portal: Portal | None = None
) -> dict[str, Any]:
    if projects.effective_portal(db, identity.user_id, portal) == "client":
        return {
            "data": reviews.view(
                db,
                identity.user_id,
                reviews.item_for(db, identity.user_id, content_id, "client"),
                "client",
            )["history"]
        }
    studio.item_context(db, identity.user_id, content_id)
    rows = db.scalars(
        select(ContentRevision)
        .where(ContentRevision.content_item_id == content_id)
        .order_by(ContentRevision.revision_number.desc())
    )
    return {
        "data": [
            {
                "id": r.id,
                "revision_number": r.revision_number,
                "content": r.content,
                "source_generation_id": r.source_generation_id,
            }
            for r in rows
        ]
    }


@router.get("/briefs/{brief_id}/studio")
def workspace(brief_id: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    b = briefs.get(db, identity.user_id, brief_id, "agency")
    snapshot = db.scalar(
        select(Snapshot).where(Snapshot.brief_id == b.id, Snapshot.version == b.version)
    )
    if not snapshot:
        return {
            "data": {
                "brief": briefs.view(db, b),
                "jobs": [],
                "proposals": [],
                "items": [],
                "automation": [],
                "brand": {},
                "provider": settings().ai_provider,
            }
        }
    jobs = db.scalars(
        select(Generation)
        .where(Generation.snapshot_id == snapshot.id)
        .order_by(Generation.created_at.desc())
        .limit(100)
    )
    props = db.scalars(
        select(Proposal)
        .where(Proposal.snapshot_id == snapshot.id)
        .order_by(Proposal.created_at, Proposal.item_index)
    )
    items = db.scalars(
        select(ContentItem)
        .join(Proposal, Proposal.id == ContentItem.source_proposal_id)
        .where(Proposal.snapshot_id == snapshot.id)
        .order_by(ContentItem.created_at)
    )
    events = db.execute(
        select(Outbox, WorkflowRun)
        .outerjoin(
            WorkflowRun,
            (WorkflowRun.event_id == Outbox.id) & (WorkflowRun.attempt == Outbox.attempts),
        )
        .where(Outbox.payload["snapshot_id"].astext == str(snapshot.id))
        .order_by(Outbox.created_at)
    )
    return {
        "data": {
            "brief": briefs.view(db, b),
            "brand": snapshot.brand,
            "provider": settings().ai_provider,
            "jobs": [studio.job_view(j) for j in jobs],
            "proposals": [studio.proposal_view(p) for p in props],
            "items": [studio.item_view(db, i) for i in items],
            "automation": [
                {
                    "event": e.event_type,
                    "delivery": e.status,
                    "run": run.status if run else None,
                    "execution_id": run.n8n_execution_id if run else None,
                }
                for e, run in events
            ],
        }
    }
