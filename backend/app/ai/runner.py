from datetime import timedelta
from time import monotonic
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.ai.contracts import GenerationFailure, validate
from app.ai.providers import Provider, adapter
from app.ai_models import ContentItem, ContentRevision, Generation, Proposal
from app.brief_models import Snapshot
from app.db import engine
from app.models import Project
from app.security import now
from app.services import agency, projects, studio

MAX_ATTEMPTS = 3


def eligible(db: Session, row: Generation) -> bool:
    snap = db.get_one(Snapshot, row.snapshot_id)
    if not studio.current(db, snap):
        return False
    if row.requested_by:
        try:
            projects.access(db, row.requested_by, row.project_id)
        except HTTPException:
            return False
    if row.direction_id:
        direction = db.get_one(Proposal, row.direction_id)
        if direction.snapshot_id != snap.id or direction.decision != "approved":
            return False
    if row.revision_id:
        rev = db.get_one(ContentRevision, row.revision_id)
        if db.get_one(ContentItem, rev.content_item_id).current_revision_id != rev.id:
            return False
    return True


def stop(row: Generation, status: str, code: str) -> None:
    row.status, row.error_code, row.completed_at = status, code, now()
    row.claim_token = row.claim_expires_at = None


def claim(db: Session) -> tuple[Generation, UUID] | None:
    t = now()
    row = db.scalar(
        select(Generation)
        .where(
            or_(
                and_(Generation.status == "pending", Generation.next_attempt_at <= t),
                and_(Generation.status == "running", Generation.claim_expires_at <= t),
            )
        )
        .order_by(Generation.next_attempt_at, Generation.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        return None
    if not eligible(db, row):
        stop(row, "cancelled", "ineligible_input")
        return None
    if row.attempt >= MAX_ATTEMPTS:
        stop(row, "failed", "worker_lease_expired")
        return None
    token = uuid4()
    row.status, row.claim_token, row.claim_expires_at = "running", token, t + timedelta(seconds=90)
    row.attempt += 1
    row.started_at = row.started_at or t
    return row, token


def execute_one(provider: Provider | None = None) -> bool:
    with Session(engine(), expire_on_commit=False) as db, db.begin():
        job = claim(db)
    if not job:
        return False
    source, token = job
    start = monotonic()
    failure = None
    result = None
    output = None
    try:
        impl = provider or adapter(source.provider, source.prompt_version)
        result = impl.generate(
            source.generation_type, source.model, source.input_snapshot, source.parameters
        )
        output = validate(source.generation_type, result.content, source.parameters)
    except GenerationFailure as err:
        failure = err
    with Session(engine()) as db, db.begin():
        agency.guard_operational_write(db)
        db.get_one(Project, source.project_id, with_for_update=True)
        row = db.get_one(Generation, source.id, with_for_update=True)
        if row.claim_token != token:
            return True
        row.latency_ms = round(1000 * (monotonic() - start))
        if not eligible(db, row):
            stop(row, "cancelled", "ineligible_input")
        elif failure:
            maximum = 2 if failure.code in {"invalid_output", "invalid_plan"} else MAX_ATTEMPTS
            if failure.retryable and row.attempt < maximum:
                row.status, row.error_code = "pending", failure.code
                row.next_attempt_at = now() + timedelta(seconds=2**row.attempt)
                row.claim_token = row.claim_expires_at = None
            else:
                stop(row, "failed", failure.code)
        else:
            assert result is not None and output is not None
            row.status, row.output, row.completed_at = "completed", output, now()
            row.claim_token = row.claim_expires_at = None
            row.error_code = None
            row.input_tokens, row.output_tokens = result.input_tokens, result.output_tokens
            for name, kind in (("creative_directions", "direction"), ("content_plan", "plan_item")):
                for i, payload in enumerate(output.get(name, [])):
                    db.add(
                        Proposal(
                            generation_id=row.id,
                            snapshot_id=row.snapshot_id,
                            item_index=i,
                            kind=kind,
                            payload=payload,
                        )
                    )
    return True
