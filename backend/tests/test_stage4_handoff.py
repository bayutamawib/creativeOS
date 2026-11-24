import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.ai.evaluation_capture import EvaluationStopped
from app.ai.phase2ec_runner import (
    REPOSITORY,
    STAGE3_RUN_A_CHECKPOINT,
    STAGE4_HANDOFF,
    PreflightError,
    load_approved_stage4_handoff,
    run_stage_four_a,
)
from app.ai.providers import Response


class CopyProvider:
    prompt_version = "creative-v2"

    def __init__(self, raw: str | None = None) -> None:
        self.raw = raw
        self.calls: list[str] = []

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        self.calls.append(kind)
        raw = self.raw or json.dumps(
            {
                "headline": "Seasonal Storyline",
                "caption": "Explore seasonal variety and simple recipe inspiration.",
                "call_to_action": "Join the waitlist to hear more.",
                "hashtags": [],
                "revision_notes": ["Kept the copy grounded in the approved brief."],
                "potential_risks": ["Human review remains required."],
            }
        )
        return Response(raw, 100, 50)


def _approval(path: Path) -> Path:
    try:
        proposal_path = str(STAGE4_HANDOFF.relative_to(REPOSITORY))
    except ValueError:
        proposal_path = str(STAGE4_HANDOFF)
    value = {
        "record_type": "owner_approval",
        "approval_status": "owner_approved",
        "approval_scope": "stage4_copywriting_evaluation_only",
        "approved_proposal_evidence": proposal_path,
        "approved_proposal_sha256": hashlib.sha256(STAGE4_HANDOFF.read_bytes()).hexdigest(),
        "source_stage3_sha256": STAGE3_RUN_A_CHECKPOINT,
        "source_stage3_editorial_acceptance": "failed",
        "stage3_model_performance_reclassified": False,
    }
    path.write_text(json.dumps(value, indent=2) + "\n")
    return path


def test_stage4_handoff_is_grounded_and_requires_approval(tmp_path: Path) -> None:
    artifact = json.loads(STAGE4_HANDOFF.read_text())
    baseline = json.loads(
        (REPOSITORY / "creativeOS-uat-evidence" / "phase2c" / "brief_analysis.json").read_text()
    )
    serialized = json.dumps(artifact["proposed_output"]).lower()
    assert "fresh fruit" not in serialized and "bounty is ready" not in serialized
    assert artifact["preserved_brief_restrictions"] == baseline["input_redacted"]["brief"]["restrictions"]
    assert all(
        "proposed" in item["visual_direction"].lower()
        and "rights" in item["visual_direction"].lower()
        for item in artifact["proposed_output"]["content_plan"]
    )
    with pytest.raises(PreflightError, match="stage4_owner_approval_required"):
        load_approved_stage4_handoff()
    plan, selected = load_approved_stage4_handoff(approval_path=_approval(tmp_path / "approval.json"))
    assert selected == 0 and len(plan["content_plan"]) == 3


def test_stage4_runner_stops_on_validation_failure(tmp_path: Path) -> None:
    approval = _approval(tmp_path / "approval.json")
    provider = CopyProvider("{}")
    evidence = tmp_path / "stage4-run-a"
    with pytest.raises(EvaluationStopped, match="validation_failed"):
        run_stage_four_a(provider, approval_path=approval, evidence_dir=evidence)
    saved = json.loads((evidence / "copywriting.json").read_text())
    assert provider.calls == ["copywriting"]
    assert saved["raw_output"] == "{}"
    assert saved["evaluated"] is False
    assert saved["evaluation_status"] == "validation_failed"


def test_stage4_runner_preserves_historical_evidence(tmp_path: Path) -> None:
    source = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "stage3-run-a" / "content_plan.json"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    provider = CopyProvider()
    output = run_stage_four_a(
        provider,
        approval_path=_approval(tmp_path / "approval.json"),
        evidence_dir=tmp_path / "stage4-run-a",
    )
    assert provider.calls == ["copywriting"] and output["hashtags"] == []
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
