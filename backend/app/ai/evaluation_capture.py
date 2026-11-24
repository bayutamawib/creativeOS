"""Durable capture boundary for bounded live-model evaluations."""

import json
from pathlib import Path
from typing import Any, NoReturn

from app.ai.contracts import GenerationFailure, validate
from app.ai.providers import Provider
from app.ai.quality import assess


class EvaluationStopped(Exception):
    """A stage stopped after preserving all available diagnostic metadata."""

    def __init__(self, category: str, record: dict[str, Any]):
        self.category = category
        self.record = record
        super().__init__(category)


def _persist(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def _stop(
    path: Path,
    record: dict[str, Any],
    *,
    category: str,
    error_code: str,
    cause: Exception,
) -> NoReturn:
    record.update(
        evaluation_status=category,
        error_code=error_code,
        diagnostic_type=type(cause).__name__,
        evaluated=False,
    )
    try:
        _persist(path, record)
    except Exception as persist_error:
        record.update(
            evaluation_status="capture_failed",
            error_code="evidence_persistence_failed",
            diagnostic_type=type(persist_error).__name__,
            evaluated=False,
        )
        raise EvaluationStopped("capture_failed", record) from persist_error
    raise EvaluationStopped(category, record) from cause


def capture_stage(
    provider: Provider,
    *,
    provider_name: str,
    kind: str,
    model: str,
    prompt_version: str,
    context: dict[str, Any],
    params: dict[str, Any],
    evidence_path: Path,
    evidence_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate once and persist raw output before any evaluation step."""
    record: dict[str, Any] = {
        "stage": kind,
        "provider": provider_name,
        "model": model,
        "prompt_version": prompt_version,
        "evaluation_status": "request_pending",
        "evaluated": False,
    }
    if evidence_metadata is not None:
        record["provenance"] = evidence_metadata
    try:
        response = provider.generate(kind, model, context, params)
    except GenerationFailure as exc:
        record["retryable"] = exc.retryable
        if exc.detail is not None:
            record["error_detail"] = exc.detail
        _stop(
            evidence_path,
            record,
            category="provider_failed",
            error_code=exc.code,
            cause=exc,
        )

    record.update(
        raw_output=response.content,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        evaluation_status="output_captured",
    )
    try:
        _persist(evidence_path, record)
    except Exception as exc:
        record.update(
            evaluation_status="capture_failed",
            error_code="evidence_persistence_failed",
            diagnostic_type=type(exc).__name__,
            evaluated=False,
        )
        raise EvaluationStopped("capture_failed", record) from exc

    try:
        output = validate(kind, response.content, params)
    except GenerationFailure as exc:
        record["validation_outcome"] = "failed"
        if exc.detail is not None:
            record["error_detail"] = exc.detail
        _stop(
            evidence_path,
            record,
            category="validation_failed",
            error_code=exc.code,
            cause=exc,
        )
    except Exception as exc:
        record["validation_outcome"] = "failed"
        _stop(
            evidence_path,
            record,
            category="validation_failed",
            error_code="validation_exception",
            cause=exc,
        )
    record.update(output=output, validation_outcome="passed", evaluation_status="validated")
    try:
        _persist(evidence_path, record)
    except Exception as exc:
        record.update(
            evaluation_status="capture_failed",
            error_code="evidence_persistence_failed",
            diagnostic_type=type(exc).__name__,
            evaluated=False,
        )
        raise EvaluationStopped("capture_failed", record) from exc

    try:
        record["claim_check"] = assess(kind, output, context["brief"])
    except Exception as exc:
        _stop(
            evidence_path,
            record,
            category="claim_check_failed",
            error_code="claim_check_exception",
            cause=exc,
        )
    record.update(evaluation_status="evaluated", evaluated=True)
    try:
        _persist(evidence_path, record)
    except Exception as exc:
        record.update(
            evaluation_status="capture_failed",
            error_code="evidence_persistence_failed",
            diagnostic_type=type(exc).__name__,
            evaluated=False,
        )
        raise EvaluationStopped("capture_failed", record) from exc
    return output
