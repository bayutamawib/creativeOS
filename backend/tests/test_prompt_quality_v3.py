import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest

from app.ai.contracts import PROMPTS_V1, PROMPTS_V2, GenerationFailure, prompt_for, validate
from app.ai.phase2ec_runner import PreflightError, run_stage_two_c
from app.ai.providers import Fixture, Response
from app.ai.quality import assess


class RunCProvider(Fixture):
    prompt_version = "creative-v3"

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
        return super().generate(kind, model, context, params)


def _evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(__file__).resolve().parents[2] / "creativeOS-uat-evidence" / "phase2e-c"
    stage_one = json.loads((root / "run-a-retry" / "brief_analysis.json").read_text())
    run_b = json.loads((root / "run-b" / "creative_strategy.json").read_text())
    return stage_one, run_b


def _brief() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[2]
        / "creativeOS-uat-evidence"
        / "phase2c"
        / "brief_analysis.json"
    )
    value = json.loads(path.read_text())["input_redacted"]["brief"]
    return cast(dict[str, Any], value)


def test_creative_v3_changes_only_strategy_prompt() -> None:
    prompt = prompt_for("creative_strategy", "creative-v3")
    assert "sensory" in prompt
    assert "functional waitlist form or URL" in prompt
    assert "explicitly labeled audience hypotheses" in prompt
    assert "conceptually distinct" in prompt
    assert "Instagram carousel, Instagram caption, and Website section" in prompt
    assert prompt_for("creative_strategy", "creative-v1") == PROMPTS_V1["creative_strategy"]
    assert prompt_for("creative_strategy", "creative-v2") == PROMPTS_V2["creative_strategy"]
    for kind in ("brief_analysis", "content_plan", "copywriting", "report_summary"):
        assert prompt_for(kind, "creative-v3") == PROMPTS_V2[kind]


def test_run_b_regression_flags_grounding_without_misclassifying_hypotheses() -> None:
    _, run_b = _evidence()
    result = assess("creative_strategy", run_b["output"], _brief())
    codes = {finding["code"] for finding in result["findings"]}
    assert result["disposition"] == "critical"
    assert "unconfirmed_sensory_attribute" in codes
    assert "unconfirmed_signup_mechanism" in codes
    assert "unconfirmed_notification_priority" in codes
    assert "audience_hypothesis" not in codes


def test_visual_proposals_are_allowed_but_asset_assertions_are_reviewed() -> None:
    brief = {"objective": "Invite home cooks to a waitlist.", "restrictions": ""}
    proposed = {"creative_directions": [{
        "visual_direction": "Proposed asset: an orchard scene if available; no actual media is supplied.",
        "audience_insight": "Home cooks may appreciate recipe inspiration.",
    }]}
    assert assess("creative_strategy", proposed, brief)["findings"] == []
    asserted = {"creative_directions": [{
        "visual_direction": "Use the provided image as the campaign hero.",
        "audience_insight": "Hypothesis: home cooks may appreciate recipe inspiration.",
    }]}
    assert "unconfirmed_asset_provenance" in {
        finding["code"] for finding in assess("creative_strategy", asserted, brief)["findings"]
    }


def test_existing_valid_response_and_strict_json_remain_compatible() -> None:
    _, run_b = _evidence()
    assert validate("creative_strategy", run_b["raw_output"], {}) == run_b["output"]
    with pytest.raises(GenerationFailure, match="duplicate_json_key:creative_directions"):
        validate(
            "creative_strategy",
            '{"creative_directions":[],"creative_directions":[]}',
            {},
        )


def test_run_c_preflight_and_provenance_preserve_history(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "creativeOS-uat-evidence" / "phase2e-c"
    historical = [
        root / "run-a-retry" / "brief_analysis.json",
        root / "run-b" / "creative_strategy.json",
    ]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in historical}
    evidence = tmp_path / "run-c"
    provider = RunCProvider()

    output = run_stage_two_c(provider, evidence_dir=evidence)

    assert provider.calls == ["creative_strategy"]
    assert "creative_directions" in output
    saved = json.loads((evidence / "creative_strategy.json").read_text())
    assert saved["prompt_version"] == "creative-v3"
    assert saved["provenance"]["source_stage1_sha256"] == before[historical[0]]
    assert saved["provenance"]["prior_stage2_sha256"] == before[historical[1]]
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in historical}
    assert not (evidence / "content_plan.json").exists()
    assert not (evidence / "copywriting.json").exists()


def test_run_c_rejects_checkpoint_mismatch_and_existing_output(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "creativeOS-uat-evidence" / "phase2e-c"
    altered = tmp_path / "creative_strategy.json"
    shutil.copyfile(root / "run-b" / "creative_strategy.json", altered)
    altered.write_bytes(altered.read_bytes() + b"\n")
    provider = RunCProvider()
    with pytest.raises(PreflightError, match="run_b_checkpoint_mismatch"):
        run_stage_two_c(provider, source_run_b=altered, evidence_dir=tmp_path / "run-c")
    assert provider.calls == []

    evidence = tmp_path / "existing-run-c"
    evidence.mkdir()
    (evidence / "creative_strategy.json").write_text("{}")
    with pytest.raises(PreflightError, match="stage2_evidence_exists"):
        run_stage_two_c(provider, evidence_dir=evidence)
    assert provider.calls == []
