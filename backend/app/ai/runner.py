from datetime import timedelta
from time import monotonic
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.ai.contracts import GenerationFailure, validate
from app.ai.providers import Provider, adapter
from app.ai.quality import assess
from app.ai.reporting import validate_summary
from app.ai_models import ContentItem, ContentRevision, Generation, Proposal
from app.brief_models import Snapshot
from app.db import engine
from app.models import Project
from app.operations_models import Outbox
from app.report_models import Report
from app.security import now
from app.services import agency, projects, studio

MAX_ATTEMPTS = 3


def eligible(db: Session, row: Generation) -> bool:
    if row.report_id:
        report = db.get_one(Report, row.report_id)
        return (
            report.status == "generating"
            and report.metrics == row.input_snapshot
            and db.get_one(Project, row.project_id).archived_at is None
            and (
                row.requested_by is None
                or bool(agency.roles(db, row.requested_by) & {"admin", "agency_manager"})
            )
        )
    assert row.snapshot_id is not None
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


def stop(db: Session, row: Generation, status: str, code: str) -> None:
    if row.report_id:
        db.get_one(Report, row.report_id).status = "failed"
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
        stop(db, row, "cancelled", "ineligible_input")
        return None
    if row.attempt >= MAX_ATTEMPTS + row.retry_allowance:
        stop(db, row, "failed", "worker_lease_expired")
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
    summary = None
    try:
        impl = provider or adapter(source.provider, source.prompt_version)
        result = impl.generate(
            source.generation_type, source.model, source.input_snapshot, source.parameters
        )
        if source.report_id:
            summary = validate_summary(result.content, source.input_snapshot)
            output = summary.model_dump(mode="json")
        else:
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
            stop(db, row, "cancelled", "ineligible_input")
        elif failure:
            maximum = 2 if failure.code in {"invalid_output", "invalid_plan"} else MAX_ATTEMPTS
            if failure.retryable and row.attempt < maximum + row.retry_allowance:
                row.status, row.error_code = "pending", failure.code
                row.next_attempt_at = now() + timedelta(seconds=2 ** min(row.attempt, 6))
                row.claim_token = row.claim_expires_at = None
            else:
                stop(db, row, "failed", failure.code)
        else:
            assert result is not None and output is not None
            row.status, row.output, row.completed_at = "completed", output, now()
            if row.snapshot_id is not None:
                row.quality_findings = assess(
                    row.generation_type, output, db.get_one(Snapshot, row.snapshot_id).fields
                )
            row.claim_token = row.claim_expires_at = None
            row.error_code = None
            row.input_tokens, row.output_tokens = result.input_tokens, result.output_tokens
            if row.report_id:
                report = db.get_one(Report, row.report_id)
                assert summary is not None
                report.narrative = "\n".join(
                    [
                        summary.executive_summary,
                        *summary.completed_work,
                        *summary.pending_activities,
                        *summary.risks,
                        *summary.recommended_next_actions,
                    ]
                )
                report.status = "draft"

                db.add(
                    Outbox(
                        event_type="report.drafted",
                        aggregate_type="report",
                        aggregate_id=report.id,
                        payload={},
                    )
                )
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
