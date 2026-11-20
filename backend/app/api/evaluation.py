from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.ai import evaluation
from app.api.deps import Database, Identity
from app.api.projects import Page
from app.quality_models import CaseResult, Evaluation, HumanScore
from app.schemas import Input
from app.services import agency

router = APIRouter(prefix="/admin/evaluations")
Score = Annotated[int, Field(ge=1, le=5, strict=True)]


class Rubric(Input):
    brief_alignment: Score
    brand_alignment: Score
    creative_usefulness: Score
    actionability: Score
    factual_grounding: bool
    safety: bool
    disposition: Literal["accepted", "revision_required"]

    @model_validator(mode="after")
    def safe_acceptance(self) -> "Rubric":
        if self.disposition == "accepted" and not (self.safety and self.factual_grounding):
            raise ValueError("Critical reviews require revision")
        return self


def overview(r: Evaluation) -> dict[str, Any]:
    return {
        k: getattr(r, k)
        for k in (
            "id",
            "created_at",
            "provider",
            "model",
            "prompt_version",
            "dataset_version",
            "dataset_hash",
            "aggregates",
        )
    }


@router.post("", status_code=201)
def run(db: Database, identity: Identity) -> dict[str, Any]:
    return {"data": overview(evaluation.run(db, identity.user_id))}


@router.get("")
def listing(db: Database, identity: Identity, page: Page = 1) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    rows = db.scalars(
        select(Evaluation)
        .order_by(Evaluation.created_at.desc(), Evaluation.id)
        .offset((page - 1) * 30)
        .limit(30)
    )
    return {"data": [overview(r) for r in rows]}


@router.get("/{key}")
def detail(key: UUID, db: Database, identity: Identity) -> dict[str, Any]:
    agency.manager_roles(db, identity.user_id)
    row = db.get(Evaluation, key)
    if not row:
        raise HTTPException(404, "Evaluation unavailable")
    cases = db.scalars(
        select(CaseResult).where(CaseResult.evaluation_id == key).order_by(CaseResult.case_key)
    ).all()
    reviews = db.scalars(
        select(HumanScore)
        .join(CaseResult, CaseResult.id == HumanScore.case_id)
        .where(CaseResult.evaluation_id == key)
    ).all()
    rubrics = [r.rubric for r in reviews]
    scored = {r.case_id for r in reviews}
    revise = {r.case_id for r in reviews if r.rubric["disposition"] == "revision_required"}
    human = {
        "reviewed": len(scored),
        "reviews": len(reviews),
        "acceptance_rate": (len(scored) - len(revise)) / len(scored) if scored else None,
        "revision_rate": len(revise) / len(scored) if scored else None,
        "mean_rubric_score": sum(
            sum(
                s[k]
                for k in (
                    "brief_alignment",
                    "brand_alignment",
                    "creative_usefulness",
                    "actionability",
                )
            )
            / 4
            for s in rubrics
        )
        / len(rubrics)
        if rubrics
        else None,
    }
    own = {r.case_id: r.rubric for r in reviews if r.reviewer_id == identity.user_id}
    return {
        "data": overview(row)
        | {
            "human": human,
            "cases": [
                {
                    k: getattr(c, k)
                    for k in (
                        "id",
                        "case_key",
                        "service",
                        "passed",
                        "sample",
                        "output",
                        "checks",
                        "latency_ms",
                    )
                }
                | {"my_review": own.get(c.id)}
                for c in cases
            ],
        }
    }


@router.put("/{key}/cases/{case_id}/review")
def score(
    key: UUID, case_id: UUID, data: Rubric, db: Database, identity: Identity
) -> dict[str, bool]:
    agency.guard_operational_write(db)
    agency.manager_roles(db, identity.user_id)
    row = db.get(CaseResult, case_id)
    if not row or row.evaluation_id != key:
        raise HTTPException(404, "Case unavailable")
    if not row.output or not row.passed and data.disposition == "accepted":
        raise HTTPException(409, "Output requires revision")
    values = data.model_dump()
    db.execute(
        insert(HumanScore)
        .values(case_id=case_id, reviewer_id=identity.user_id, rubric=values)
        .on_conflict_do_update(index_elements=["case_id", "reviewer_id"], set_={"rubric": values})
    )
    agency.audit(
        db, identity.user_id, "evaluation.reviewed", case_id, {"disposition": data.disposition}
    )
    return {"data": True}
