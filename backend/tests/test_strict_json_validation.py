import json
from pathlib import Path
from typing import Any

import pytest

from app.ai import evaluation_capture
from app.ai.contracts import SCHEMAS, GenerationFailure, validate
from app.ai.evaluation_capture import EvaluationStopped, capture_stage
from app.ai.providers import Response

VALID_ANALYSIS = {
    "objective_summary": "Invite home cooks to a waitlist.",
    "target_audience": {"description": "Home cooks", "primary_needs": []},
    "key_themes": ["Seasonal variety"],
    "content_pillars": ["Recipe inspiration"],
    "missing_information": [],
    "potential_risks": [],
    "creative_constraints": ["Do not invent product claims."],
}


class MockGroq:
    def __init__(self, content: str):
        self.content = content

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        return Response(self.content, 100, 50)


def test_valid_json_preserves_existing_validation_behavior() -> None:
    assert validate("brief_analysis", json.dumps(VALID_ANALYSIS), {}) == VALID_ANALYSIS


@pytest.mark.parametrize("kind", SCHEMAS)
def test_duplicate_keys_are_rejected_for_every_ai_stage(kind: str) -> None:
    raw = '{"outer":{"repeated":1,"repeated":2}}'
    with pytest.raises(GenerationFailure, match="duplicate_json_key:repeated") as failure:
        validate(kind, raw, {})
    assert failure.value.code == "duplicate_json_key"
    assert failure.value.detail == "repeated"


def test_nested_duplicate_is_captured_before_validation_and_claim_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = tmp_path / "brief_analysis.json"
    claim_check_called = False
    raw = json.dumps(VALID_ANALYSIS).replace(
        '"description": "Home cooks"',
        '"description": "Home cooks", "description": "Overwritten audience"',
    )

    def claim_check(*_args: Any) -> dict[str, Any]:
        nonlocal claim_check_called
        claim_check_called = True
        return {}

    monkeypatch.setattr(evaluation_capture, "assess", claim_check)
    with pytest.raises(EvaluationStopped, match="validation_failed"):
        capture_stage(
            MockGroq(raw),
            provider_name="groq",
            kind="brief_analysis",
            model="openai/gpt-oss-20b",
            prompt_version="creative-v2",
            context={"brief": {"objective": "Invite home cooks to a waitlist."}},
            params={"temperature": 0.2, "max_output_tokens": 1200},
            evidence_path=evidence,
        )

    saved = json.loads(evidence.read_text())
    assert saved["raw_output"] == raw
    assert saved["evaluation_status"] == "validation_failed"
    assert saved["validation_outcome"] != "passed"
    assert saved["error_code"] == "duplicate_json_key"
    assert saved["error_detail"] == "description"
    assert saved["evaluated"] is False
    assert "claim_check" not in saved and claim_check_called is False
