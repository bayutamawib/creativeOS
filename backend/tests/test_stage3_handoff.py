import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.ai.contracts import strict_json_loads, validate
from app.ai.phase2ec_runner import (
    STAGE3_APPROVAL,
    STAGE3_HANDOFF,
    PreflightError,
    load_approved_stage3_handoff,
    run_stage_three_a,
)
from app.ai.providers import Response
from app.ai.quality import assess

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "creativeOS-uat-evidence" / "phase2c" / "brief_analysis.json"
STAGE_ONE = (
    ROOT / "creativeOS-uat-evidence" / "phase2e-c" / "run-a-retry" / "brief_analysis.json"
)
RUN_C = ROOT / "creativeOS-uat-evidence" / "phase2e-c" / "run-c" / "creative_strategy.json"


class PlanProvider:
    prompt_version = "creative-v2"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        self.calls.append(kind)
        items = []
        for index, (title, channel, format_name) in enumerate(
            (
                ("Seasonal Storyline", "Instagram", "Carousel"),
                ("Warm Invitation", "Instagram", "Caption"),
                ("Kitchen Companion", "Website", "Website section"),
            )
        ):
            items.append(
                {
                    "title": title,
                    "content_pillar": "Seasonal variety and recipe inspiration",
                    "channel": channel,
                    "content_format": format_name,
                    "objective": "Invite home cooks to the informational waitlist.",
                    "key_message": "Seasonal variety and simple recipe inspiration.",
                    "draft_caption": "Explore seasonal variety and simple recipe inspiration.",
                    "visual_direction": "Proposed general imagery requiring rights confirmation.",
                    "call_to_action": "Join the waitlist to hear more.",
                    "suggested_day_offset": index,
                }
            )
        return Response(json.dumps({"content_plan": items}), 100, 50)


def _artifact() -> dict[str, Any]:
    return cast(dict[str, Any], strict_json_loads(STAGE3_HANDOFF.read_text()))


def _brief() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(BASELINE.read_text())["input_redacted"]["brief"])


def test_handoff_removes_critical_claims_and_preserves_brief_restrictions() -> None:
    artifact = _artifact()
    output = validate("creative_strategy", json.dumps(artifact["proposed_output"]), {})
    result = assess("creative_strategy", output, _brief())
    serialized = json.dumps(output).lower()

    assert result["disposition"] != "critical"
    assert all(
        term not in serialized
        for term in ("apples", "pears", "figs", "apple crumble", "ripe fruit")
    )
    assert artifact["preserved_brief_restrictions"] == _brief()["restrictions"]
    assert all(
        direction["audience_insight"].startswith("Hypothesis:")
        for direction in output["creative_directions"]
    )
    assert all(
        "proposed" in direction["visual_direction"].lower()
        and "rights" in direction["visual_direction"].lower()
        for direction in output["creative_directions"]
    )


def test_handoff_retains_failed_source_provenance_and_change_reasons() -> None:
    artifact = _artifact()
    assert artifact["source_stage2_editorial_acceptance"] == "failed"
    assert artifact["source_stage2_evidence"].endswith("run-c/creative_strategy.json")
    assert artifact["source_stage2_sha256"] == hashlib.sha256(RUN_C.read_bytes()).hexdigest()
    assert artifact["authoritative_sources"]["stage1_sha256"] == hashlib.sha256(
        STAGE_ONE.read_bytes()
    ).hexdigest()
    assert artifact["exact_changes"]
    assert all(change["reason"] for change in artifact["exact_changes"])


def test_pending_handoff_requires_owner_approval() -> None:
    with pytest.raises(PreflightError, match="stage3_owner_approval_required"):
        load_approved_stage3_handoff()


def test_separate_owner_approval_unlocks_only_stage3_handoff() -> None:
    output = load_approved_stage3_handoff(approval_path=STAGE3_APPROVAL)
    proposal = _artifact()
    assert output == proposal["proposed_output"]
    assert proposal["human_review_status"] == "pending_owner_approval"
    approval = json.loads(STAGE3_APPROVAL.read_text())
    assert approval["stage2_model_performance_reclassified"] is False
    assert approval["stage4_execution_authorized"] is False


def test_stage_three_runner_uses_approved_handoff_only(tmp_path: Path) -> None:
    provider = PlanProvider()
    evidence = tmp_path / "stage3-run-a"

    output = run_stage_three_a(provider, evidence_dir=evidence)

    assert provider.calls == ["content_plan"]
    assert len(output["content_plan"]) == 3
    saved = json.loads((evidence / "content_plan.json").read_text())
    assert saved["evaluation_status"] == "evaluated"
    assert saved["provenance"]["stage2_input_type"] == "human_reviewed_owner_approved_handoff"
    assert saved["provenance"]["stage2_model_editorial_acceptance"] == "failed"
    assert saved["provenance"]["stage2_model_performance_reclassified"] is False
    assert not (evidence / "copywriting.json").exists()


def test_explicitly_approved_copy_can_pass_guard_without_changing_history(tmp_path: Path) -> None:
    historical = [STAGE_ONE, RUN_C]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in historical}
    artifact = _artifact()
    artifact["human_review_status"] = "owner_approved"
    artifact["downstream_execution_authorized"] = True
    approved = tmp_path / "approved_handoff.json"
    approved.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")

    output = load_approved_stage3_handoff(approved)

    assert len(output["creative_directions"]) == 3
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in historical}
