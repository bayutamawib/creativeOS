"""Run the versioned synthetic suite against the production schemas and authorization services."""

import hashlib
import json
import secrets
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.ai.contracts import PROMPT_VERSION, SCHEMAS, GenerationFailure, validate
from app.ai.providers import adapter
from app.ai.reporting import grounded
from app.brief_models import Brief, Snapshot
from app.models import Client, ClientMembership, Project, User
from app.quality_models import CaseResult, Evaluation
from app.security import hash_password
from app.services import agency, studio

DATASET = Path(__file__).parent / "datasets/creative-v1.json"
SERVICES = ("brief_analysis", "creative_strategy", "content_plan", "copywriting", "report_summary")


def assess(kind: str, output: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if kind == "report_summary":
        grounded(ctx, output)
        return True
    b = ctx["brief"]
    if kind == "brief_analysis":
        return bool(
            output["objective_summary"] == b["objective"]
            and (not b["restrictions"] or b["restrictions"] in output["creative_constraints"])
        )
    if kind == "creative_strategy":
        return all(
            d["key_message"] == b["objective"] and b["channel"] in d["suggested_channels"]
            for d in output["creative_directions"]
        )
    if kind == "content_plan":
        return all(
            i["objective"] == b["objective"] and i["key_message"] == ctx["direction"]["key_message"]
            for i in output["content_plan"]
        )
    return bool(
        output["headline"] == ctx["plan_item"]["title"]
        and output["caption"] == ctx["plan_item"]["draft_caption"]
    )


def pipeline(key: UUID, b: dict[str, Any]) -> list[CaseResult]:
    provider = adapter("fixture", PROMPT_VERSION)
    ctx: dict[str, Any] = {"brief": b}
    params = {"channels": [b["channel"]], "target_count": 2}
    rows = []
    metrics = {
        "period": "Synthetic week",
        "completed_tasks": 3,
        "open_tasks": 2,
        "overdue_tasks": 1,
    }
    for kind in SERVICES:
        source = metrics if kind == "report_summary" else ctx
        prereq = {
            "creative_strategy": "analysis",
            "content_plan": "direction",
            "copywriting": "plan_item",
        }.get(kind)
        checks: dict[str, Any] = {
            "attempted": False,
            "schema": False,
            "required_fields": False,
            "grounded": False,
        }
        start = perf_counter()
        output = None
        if prereq and prereq not in ctx:
            checks["error"] = "missing_upstream_output"
        else:
            checks["attempted"] = True
            try:
                raw = provider.generate(kind, "fixture-v1", source, params)
                output = validate(kind, raw.content, params)
                checks["schema"] = True
                checks["required_fields"] = all(
                    k in output for k, v in SCHEMAS[kind].model_fields.items() if v.is_required()
                )
                checks["grounded"] = assess(kind, output, source)
            except GenerationFailure as failure:
                checks["error"] = failure.code
        passed = all(checks[k] for k in ("schema", "required_fields", "grounded"))
        rows.append(
            CaseResult(
                evaluation_id=key,
                case_key=b["id"] + "/" + kind,
                service=kind,
                passed=passed,
                checks=checks,
                sample={"brief": b, "metrics": metrics} if kind == "report_summary" else dict(ctx),
                output=output,
                latency_ms=round((perf_counter() - start) * 1000),
            )
        )
        if passed and output:
            if kind == "brief_analysis":
                ctx["analysis"] = output
            if kind == "creative_strategy":
                ctx["direction"] = output["creative_directions"][0]
            if kind == "content_plan":
                ctx["plan_item"] = output["content_plan"][0]
    return rows


def guard_controls(db: Session, actor: UUID) -> dict[str, bool]:
    # The real services see synthetic project rows inside a savepoint. None can commit.
    sp = db.begin_nested()
    try:
        c = Client(company_name="Evaluation sample")
        db.add(c)
        db.flush()
        p = Project(client_id=c.id, name="Synthetic guard checks")
        db.add(p)
        db.flush()
        b = Brief(
            client_id=c.id,
            project_id=p.id,
            created_by=actor,
            title="Sample",
            objective="Sample",
            requirements={},
            status="approved",
        )
        db.add(b)
        db.flush()
        snap = Snapshot(
            brief_id=b.id,
            client_id=c.id,
            project_id=p.id,
            version=b.version,
            approved_by=actor,
            fields={"requested_item_count": 1, "preferred_channels": ["Website"]},
            brand={},
            attachments=[],
        )
        db.add(snap)
        db.flush()
        viewer = User(
            email=f"evaluation-{uuid4()}@example.invalid",
            full_name="Synthetic client member",
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(viewer)
        db.flush()
        db.add(ClientMembership(client_id=c.id, user_id=viewer.id, role="client_member"))
        db.flush()
        results = {}
        for name, who, kind, options, code in [
            (
                "unauthorized_generation",
                viewer.id,
                "brief_analysis",
                studio.Options.model_validate({}),
                403,
            ),
            ("unapproved_direction", actor, "content_plan", studio.Options.model_validate({}), 409),
            (
                "stale_snapshot",
                actor,
                "brief_analysis",
                studio.Options.model_validate({"snapshot_id": snap.id}),
                409,
            ),
        ]:
            if name == "stale_snapshot":
                b.version += 1
                db.flush()
            try:
                studio.manual(db, who, b.id, kind, name, options)
            except HTTPException as err:
                results[name] = err.status_code == code
            else:
                results[name] = False
        return results
    finally:
        sp.rollback()


def controls(db: Session, actor: UUID) -> dict[str, bool]:
    result = guard_controls(db, actor)
    for key, value in [
        ("malformed_json", "{"),
        ("missing_required_field", '{"executive_summary":"Draft"}'),
    ]:
        try:
            validate("report_summary", value, {})
        except GenerationFailure as err:
            result[key] = err.code == "invalid_output"
        else:
            result[key] = False
    try:
        grounded(
            {"period": "Synthetic week", "completed_tasks": 3},
            {
                "executive_summary": "Revenue doubled.",
                "completed_work": [],
                "pending_activities": [],
                "risks": [],
                "recommended_next_actions": [],
            },
        )
    except GenerationFailure as err:
        result["unsupported_report_claim"] = err.code == "unsupported_report_claim"
    else:
        result["unsupported_report_claim"] = False
    return result


def run(db: Session, actor: UUID) -> Evaluation:
    agency.guard_operational_write(db)
    agency.manager_roles(db, actor)
    raw = DATASET.read_bytes()
    data = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:version,5))"),
        {"version": data["version"]},
    )
    prior = db.scalar(
        select(Evaluation.dataset_hash)
        .where(Evaluation.dataset_version == data["version"])
        .limit(1)
    )
    if prior and prior != digest:
        raise HTTPException(409, "Dataset contents changed without a new version")
    row = Evaluation(
        requested_by=actor,
        provider="fixture",
        model="fixture-v1",
        prompt_version=PROMPT_VERSION,
        dataset_version=data["version"],
        dataset_hash=digest,
        aggregates={},
    )
    db.add(row)
    db.flush()
    outputs = [case for b in data["briefs"] for case in pipeline(row.id, b)]
    guard = controls(db, actor)
    if set(guard) != set(data["controls"]):
        raise ValueError("Dataset control inventory mismatch")
    tests = [
        CaseResult(
            evaluation_id=row.id,
            case_key=k,
            service="control",
            passed=guard[k],
            checks={"rejected_as_expected": guard[k]},
            sample={"control": k},
            output=None,
            latency_ms=0,
        )
        for k in data["controls"]
    ]
    db.add_all(outputs + tests)
    attempted = sum(c.checks["attempted"] for c in outputs)
    valid = sum(c.checks["schema"] for c in outputs)
    row.aggregates = {
        "briefs": len(data["briefs"]),
        "outputs": len(outputs),
        "attempted": attempted,
        "schema_valid": valid,
        "schema_validity_rate": valid / attempted if attempted else None,
        "generation_success_rate": valid / len(outputs) if outputs else None,
        "required_complete": sum(c.checks["required_fields"] for c in outputs),
        "grounding_passed": sum(c.passed for c in outputs),
        "controls_passed": sum(guard.values()),
        "controls": len(guard),
        "passed": sum(c.passed for c in outputs + tests),
        "total": len(outputs + tests),
        "generation_latency_ms": sum(c.latency_ms for c in outputs),
        "tokens": None,
    }
    agency.audit(db, actor, "evaluation.executed", row.id, {"dataset": data["version"]})
    return row
