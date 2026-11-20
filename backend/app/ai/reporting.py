"""Validate report narratives against the frozen PostgreSQL evidence used for generation."""

from typing import Any

from pydantic import Field

from app.ai.contracts import (
    PROMPT_VERSION,
    TEMPERATURES,
    GenerationFailure,
    Structured,
    Summary,
    Title,
    validate,
)
from app.ai.providers import adapter
from app.config import settings


class VerifiedMetrics(Structured):
    period: Title
    completed_tasks: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    overdue_tasks: int = Field(ge=0)


def summarize(metrics: VerifiedMetrics) -> Summary:
    config = settings()
    response = adapter(config.ai_provider, PROMPT_VERSION).generate(
        "report_summary",
        config.ai_model,
        metrics.model_dump(),
        {
            "temperature": TEMPERATURES["report_summary"],
            "max_output_tokens": config.ai_max_output_tokens,
            **instructions(metrics.model_dump()),
        },
    )
    return validate_summary(response.content, metrics.model_dump())


def evidence(metrics: dict[str, Any]) -> list[str]:
    return [
        f"Draft summary for {metrics['period']}.",
        "Review the recorded project metrics.",
        *[
            f"{key.replace('_', ' ').capitalize()}: {value}"
            for key, value in metrics.items()
            if type(value) is int
        ],
    ]


def grounded(metrics: dict[str, Any], output: dict[str, Any]) -> Summary:
    summary = Summary.model_validate(output)
    allowed = set(evidence(metrics))
    sentences = [
        summary.executive_summary,
        *summary.completed_work,
        *summary.pending_activities,
        *summary.risks,
        *summary.recommended_next_actions,
    ]
    if any(s not in allowed for s in sentences):
        raise GenerationFailure("unsupported_report_claim", True)
    return summary


def instructions(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed_statements": evidence(metrics),
        "statement_policy": "Select exact statements from allowed_statements for every section. Omit unsupported risks and recommendations.",
    }


def validate_summary(raw: str, metrics: dict[str, Any]) -> Summary:
    return grounded(metrics, validate("report_summary", raw, {}))
