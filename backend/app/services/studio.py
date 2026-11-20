import hashlib
import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.ai.contracts import PROMPT_VERSION, TEMPERATURES
from app.ai_models import ContentItem, ContentRevision, Generation, Proposal
from app.brief_inputs import Channel, Paragraph
from app.brief_models import Brief, Snapshot
from app.config import settings
from app.models import Project
from app.operations_models import Outbox, WorkflowRun
from app.project_models import Task
from app.schemas import Input
from app.security import now
from app.services import agency, briefs, projects


class Options(Input):
    snapshot_id: UUID | None = None
    direction_proposal_id: UUID | None = None
    revision_id: UUID | None = None
    target_count: int | None = Field(None, ge=1, le=10)
    channels: list[Channel] | None = Field(None, min_length=1, max_length=8)
    feedback: Paragraph | None = None
    include: list[str] = Field(default_factory=list, max_length=8)


def current(db: Session, snap: Snapshot) -> bool:
    b = db.get_one(Brief, snap.brief_id)
    return (
        b.status == "approved"
        and b.version == snap.version
        and db.get_one(Project, snap.project_id).archived_at is None
    )


def approved(db: Session, b: Brief) -> Snapshot:
    snap = db.scalar(
        select(Snapshot).where(Snapshot.brief_id == b.id, Snapshot.version == b.version)
    )
    if b.status != "approved" or snap is None:
        raise HTTPException(409, "The latest brief version needs approval")
    return snap


def output_job(
    db: Session, snapshot_id: UUID, kind: str, event_id: UUID | None = None
) -> Generation | None:
    st = select(Generation).where(
        Generation.snapshot_id == snapshot_id,
        Generation.generation_type == kind,
        Generation.status == "completed",
    )
    if event_id:
        st = st.where(Generation.event_id == event_id)
    return db.scalar(st.order_by(Generation.completed_at.desc(), Generation.id).limit(1))


def enqueue(
    db: Session,
    snap: Snapshot,
    kind: str,
    key: str,
    options: Options,
    *,
    actor: UUID | None = None,
    run: WorkflowRun | None = None,
    content: ContentItem | None = None,
) -> Generation:
    if (actor is None) == (run is None):
        raise ValueError("Exactly one generation requester is required")
    scope = str(actor) if actor else "n8n:WF-B"
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key,3))"), {"key": scope + kind + key}
    )
    if not current(db, snap) or options.snapshot_id and options.snapshot_id != snap.id:
        raise HTTPException(409, "Approved snapshot is stale")
    context = {"brief": snap.fields, "brand": snap.brand, "attachments": snap.attachments}
    params: dict[str, Any] = {
        "target_count": options.target_count or snap.fields["requested_item_count"],
        "channels": options.channels or snap.fields["preferred_channels"] or ["Website"],
        "feedback": options.feedback,
        "include": options.include,
        "temperature": TEMPERATURES[kind],
        "max_output_tokens": settings().ai_max_output_tokens,
    }
    if kind != "content_plan" and (
        options.direction_proposal_id or options.target_count or options.channels or options.include
    ):
        raise HTTPException(422, "Plan options require content planning")
    if kind != "copywriting" and (options.revision_id or options.feedback):
        raise HTTPException(422, "Revision options require copywriting")
    direction_id = options.direction_proposal_id
    revision_id = None
    if content:
        revision_id = options.revision_id or content.current_revision_id
    inputs = {
        "snapshot": str(snap.id),
        "content": str(content.id) if content else None,
        "revision": str(revision_id),
        "options": options.model_dump(mode="json"),
        "event": str(run.event_id) if run else None,
    }
    fp = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    old = db.scalar(
        select(Generation).where(
            Generation.requester_scope == scope,
            Generation.generation_type == kind,
            Generation.idempotency_key == key,
        )
    )
    if old:
        if old.fingerprint != fp:
            raise HTTPException(409, "Idempotency key already used for different inputs")
        return old
    if kind == "content_plan":
        prop = db.get(Proposal, direction_id) if direction_id else None
        if (
            not prop
            or prop.snapshot_id != snap.id
            or prop.kind != "direction"
            or prop.decision != "approved"
        ):
            raise HTTPException(409, "Select an approved direction from this snapshot")
        context["direction"] = prop.payload
    if kind == "copywriting":
        if (
            not content
            or not content.current_revision_id
            or options.revision_id
            and options.revision_id != content.current_revision_id
        ):
            raise HTTPException(409, "Content revision changed")
        item = db.get_one(Proposal, content.source_proposal_id)
        if item.snapshot_id != snap.id:
            raise HTTPException(409, "Draft belongs to an earlier brief version")
        plan = db.get_one(Generation, item.generation_id)
        direction_id = plan.direction_id
        if not direction_id:
            raise HTTPException(409, "Direction unavailable")
        context.update(
            plan_item=item.payload,
            direction=db.get_one(Proposal, direction_id).payload,
            revision=db.get_one(ContentRevision, content.current_revision_id).content,
        )
        revision_id = content.current_revision_id
    if kind == "creative_strategy":
        a = output_job(db, snap.id, "brief_analysis", run.event_id if run else None)
        if not a or not a.output:
            raise HTTPException(409, "A completed analysis is required")
        context["analysis"] = a.output
        params["analysis_generation_id"] = str(a.id)
    if (
        actor
        and (
            db.scalar(
                select(func.count())
                .select_from(Generation)
                .where(
                    Generation.project_id == snap.project_id,
                    Generation.created_at >= now() - timedelta(hours=1),
                )
            )
            or 0
        )
        >= 100
    ):
        raise HTTPException(429, "Project generation limit reached")
    row = Generation(
        snapshot_id=snap.id,
        project_id=snap.project_id,
        client_id=snap.client_id,
        generation_type=kind,
        requester_scope=scope,
        requested_by=actor,
        service_identity=None if actor else "n8n:WF-B",
        event_id=run.event_id if run else None,
        run_id=run.id if run else None,
        idempotency_key=key,
        fingerprint=fp,
        input_snapshot=context,
        parameters=params,
        provider=settings().ai_provider,
        model=settings().ai_model,
        prompt_version=PROMPT_VERSION,
        direction_id=direction_id,
        revision_id=revision_id,
    )
    db.add(row)
    db.flush()
    return row


def manual(
    db: Session,
    actor: UUID,
    brief_id: UUID,
    kind: str,
    key: str,
    options: Options,
    content: ContentItem | None = None,
) -> Generation:
    b = briefs.get(db, actor, brief_id, "agency", write=True)
    return enqueue(db, approved(db, b), kind, key, options, actor=actor, content=content)


def job_view(job: Generation) -> dict[str, Any]:
    return {
        k: getattr(job, k)
        for k in (
            "id",
            "project_id",
            "snapshot_id",
            "generation_type",
            "provider",
            "model",
            "prompt_version",
            "status",
            "output",
            "error_code",
            "attempt",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "requested_by",
            "service_identity",
            "event_id",
            "run_id",
            "direction_id",
            "revision_id",
            "parameters",
            "created_at",
        )
    }


def scoped_job(db: Session, actor: UUID, key: UUID) -> Generation:
    job = db.get(Generation, key)
    if not job:
        raise HTTPException(404, "Generation not found")
    projects.access(db, actor, job.project_id)
    return job


def proposal_view(row: Proposal) -> dict[str, Any]:
    return {
        k: getattr(row, k)
        for k in (
            "id",
            "generation_id",
            "snapshot_id",
            "kind",
            "payload",
            "decision",
            "decided_by",
            "decided_at",
        )
    }


def decide(db: Session, actor: UUID, key: UUID, decision: str) -> Proposal:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    prop = db.get(Proposal, key)
    if not prop:
        raise HTTPException(404, "Proposal unavailable")
    snap = db.get_one(Snapshot, prop.snapshot_id)
    p = projects.access(db, actor, snap.project_id, write=True)
    db.refresh(prop)
    if not current(db, snap):
        raise HTTPException(409, "The proposal snapshot is stale")
    if prop.decision == decision:
        return prop
    if prop.decision != "pending":
        raise HTTPException(409, "Proposal already decided")
    if decision == "approved" and prop.kind == "direction":
        selected = db.scalar(
            select(Proposal.id)
            .where(
                Proposal.snapshot_id == snap.id,
                Proposal.kind == "direction",
                Proposal.decision == "approved",
            )
            .limit(1)
        )
        if selected:
            raise HTTPException(409, "A direction was already selected for this snapshot")
        db.add(
            Outbox(
                event_type="creative_direction.approved",
                aggregate_type="proposal",
                aggregate_id=prop.id,
                payload={"snapshot_id": str(snap.id)},
            )
        )
    if decision == "approved" and prop.kind == "plan_item":
        for step in ["Prepare draft", "Review draft"]:
            db.add(
                Task(
                    project_id=p.id,
                    client_id=p.client_id,
                    title=step + " · " + prop.payload["title"],
                    created_by=actor,
                    source_proposal_id=prop.id,
                    template_step=step,
                )
            )
    prop.decision, prop.decided_by, prop.decided_at = decision, actor, now()
    projects.change_log(db, actor, p, "proposal." + decision, prop.id, {"kind": prop.kind})
    return prop


def item_view(db: Session, item: ContentItem) -> dict[str, Any]:
    revision = (
        db.get_one(ContentRevision, item.current_revision_id) if item.current_revision_id else None
    )
    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "brief_id": item.brief_id,
        "source_proposal_id": item.source_proposal_id,
        "current_revision_id": item.current_revision_id,
        "revision_number": revision.revision_number if revision else None,
        "content": revision.content if revision else None,
    }


def draft(db: Session, actor: UUID, pid: UUID, proposal_id: UUID) -> ContentItem:
    p = briefs.context(db, actor, pid, "agency", write=True)
    prop = db.get(Proposal, proposal_id)
    if not prop or prop.kind != "plan_item":
        raise HTTPException(404, "Plan item unavailable")
    snap = db.get_one(Snapshot, prop.snapshot_id)
    if snap.project_id != p.id:
        raise HTTPException(404, "Plan item unavailable")
    if prop.decision != "approved" or not current(db, snap):
        raise HTTPException(409, "Select a current approved plan item")
    old = db.scalar(select(ContentItem).where(ContentItem.source_proposal_id == prop.id))
    if old:
        return old
    item = ContentItem(
        brief_id=snap.brief_id,
        project_id=p.id,
        client_id=p.client_id,
        source_proposal_id=prop.id,
        title=prop.payload["title"],
        channel=prop.payload["channel"],
        content_type=prop.payload["content_format"],
    )
    db.add(item)
    db.flush()
    rev = ContentRevision(
        content_item_id=item.id,
        revision_number=1,
        content=prop.payload,
        created_by=actor,
        source_generation_id=prop.generation_id,
    )
    db.add(rev)
    db.flush()
    item.current_revision_id = rev.id
    projects.change_log(db, actor, p, "content.draft_created", item.id)
    return item


def item_context(db: Session, actor: UUID, key: UUID, write: bool = False) -> ContentItem:
    item = db.get(ContentItem, key)
    if not item:
        raise HTTPException(404, "Draft not found")
    briefs.context(db, actor, item.project_id, "agency", write=write)
    db.refresh(item)
    return item


def save_copy(db: Session, actor: UUID, key: UUID, generation_id: UUID) -> ContentItem:
    item = item_context(db, actor, key, True)
    job = scoped_job(db, actor, generation_id)
    if (
        job.generation_type != "copywriting"
        or job.status != "completed"
        or not job.output
        or not job.revision_id
    ):
        raise HTTPException(409, "A completed copy suggestion is required")
    parent = db.get_one(ContentRevision, job.revision_id)
    if parent.content_item_id != item.id:
        raise HTTPException(404, "Suggestion not found")
    existing = db.scalar(
        select(ContentRevision.id).where(
            ContentRevision.content_item_id == key, ContentRevision.source_generation_id == job.id
        )
    )
    if existing:
        return item
    if parent.id != item.current_revision_id or not current(
        db, db.get_one(Snapshot, job.snapshot_id)
    ):
        raise HTTPException(409, "The suggestion uses stale inputs")
    rev = ContentRevision(
        content_item_id=key,
        revision_number=parent.revision_number + 1,
        content=job.output,
        created_by=actor,
        source_generation_id=job.id,
    )
    db.add(rev)
    db.flush()
    from app.services.reviews import link_files, supersede

    link_files(db, item, parent.id, rev.id)
    supersede(db, item)
    item.current_revision_id = rev.id
    projects.change_log(
        db, actor, db.get_one(Project, item.project_id), "content.revision_saved", rev.id
    )
    return item
