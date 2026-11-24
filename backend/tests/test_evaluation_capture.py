import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from app.ai import evaluation_capture, phase2ec_runner
from app.ai.contracts import GenerationFailure, validate
from app.ai.evaluation_capture import EvaluationStopped, capture_stage
from app.ai.phase2ec_runner import PreflightError, run_four_stage
from app.ai.providers import Fixture, Response
from app.ai.quality import assess

BRIEF = {
    "title": "Morrow Orchard",
    "objective": "Invite home cooks to a seasonal fruit-box waitlist.",
    "target_audience": "Home cooks",
    "key_message": "Join the seasonal waitlist.",
    "content_type": "Campaign",
    "restrictions": "Do not name exact fruit varieties.",
}
OUTPUT = {
    "objective_summary": BRIEF["objective"],
    "target_audience": {"description": "Home cooks", "primary_needs": []},
    "key_themes": ["Seasonal waitlist"],
    "content_pillars": ["Seasonal anticipation"],
    "missing_information": ["Signup destination is unconfirmed."],
    "potential_risks": [],
    "creative_constraints": [BRIEF["restrictions"]],
}


class MockGroq:
    prompt_version = "creative-v2"

    def __init__(self, content: str):
        self.content = content

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        return Response(content=self.content, input_tokens=1189, output_tokens=948)


class TrackingFixture(Fixture):
    prompt_version = "creative-v2"

    def __init__(self, fail_at: int | None = None):
        self.calls: list[str] = []
        self.fail_at = fail_at

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        self.calls.append(kind)
        if self.fail_at == len(self.calls):
            raise GenerationFailure("provider_unavailable", True)
        return super().generate(kind, model, context, params)


def _capture(
    provider: MockGroq,
    evidence: Path,
    *,
    content: str | None = None,
) -> dict[str, Any]:
    if content is not None:
        provider.content = content
    return capture_stage(
        provider,
        provider_name="groq",
        kind="brief_analysis",
        model="openai/gpt-oss-20b",
        prompt_version="creative-v2",
        context={"brief": BRIEF},
        params={"temperature": 0.2, "max_output_tokens": 1200},
        evidence_path=evidence,
    )


def test_captures_provider_content_before_validation_and_claim_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = tmp_path / "brief_analysis.json"
    events: list[str] = []

    def checked_validate(kind: str, raw: str, params: dict[str, Any]) -> dict[str, Any]:
        captured = json.loads(evidence.read_text())
        assert captured["raw_output"] == raw
        assert captured["evaluation_status"] == "output_captured"
        assert captured["evaluated"] is False
        events.append("validate")
        return validate(kind, raw, params)

    def checked_assess(
        kind: str, output: dict[str, Any], brief: dict[str, Any]
    ) -> dict[str, Any]:
        captured = json.loads(evidence.read_text())
        assert captured["validation_outcome"] == "passed"
        assert captured["evaluation_status"] == "validated"
        assert captured["evaluated"] is False
        events.append("assess")
        return assess(kind, output, brief)

    monkeypatch.setattr(evaluation_capture, "validate", checked_validate)
    monkeypatch.setattr(evaluation_capture, "assess", checked_assess)
    raw = json.dumps(OUTPUT)
    result = _capture(MockGroq(raw), evidence)

    saved = json.loads(evidence.read_text())
    assert result == OUTPUT and events == ["validate", "assess"]
    assert saved["raw_output"] == raw
    assert saved["prompt_version"] == "creative-v2"
    assert saved["evaluation_status"] == "evaluated" and saved["evaluated"] is True


def test_failure_categories_are_distinct(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider_path = tmp_path / "provider.json"

    class ProviderFailure(MockGroq):
        def generate(self, *args: Any) -> Response:
            raise GenerationFailure("provider_unavailable", True)

    with pytest.raises(EvaluationStopped) as provider_error:
        _capture(ProviderFailure(""), provider_path)
    assert provider_error.value.category == "provider_failed"
    assert json.loads(provider_path.read_text())["evaluation_status"] == "provider_failed"

    validation_path = tmp_path / "validation.json"
    with pytest.raises(EvaluationStopped) as validation_error:
        _capture(MockGroq("{invalid"), validation_path)
    validation = json.loads(validation_path.read_text())
    assert validation_error.value.category == "validation_failed"
    assert validation["evaluation_status"] == "validation_failed"
    assert validation["evaluated"] is False and "claim_check" not in validation

    claim_path = tmp_path / "claim.json"
    monkeypatch.setattr(
        evaluation_capture,
        "assess",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic claim failure")),
    )
    with pytest.raises(EvaluationStopped) as claim_error:
        _capture(MockGroq(json.dumps(OUTPUT)), claim_path)
    claim = json.loads(claim_path.read_text())
    assert claim_error.value.category == "claim_check_failed"
    assert claim["evaluation_status"] == "claim_check_failed"
    assert claim["evaluated"] is False

    monkeypatch.setattr(evaluation_capture, "_persist", lambda *_args: (_ for _ in ()).throw(OSError()))
    with pytest.raises(EvaluationStopped) as capture_error:
        _capture(MockGroq(json.dumps(OUTPUT)), tmp_path / "capture.json")
    assert capture_error.value.category == "capture_failed"
    assert capture_error.value.record["evaluation_status"] == "capture_failed"
    assert capture_error.value.record["evaluated"] is False


def test_four_stage_runner_uses_capture_boundary_and_preserves_existing_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    evidence = tmp_path / "run-a-retry"
    canonical = phase2ec_runner.REPOSITORY / "creativeOS-uat-evidence"
    preserved = sorted((canonical / "phase2c").glob("*.json")) + sorted(
        (canonical / "phase2e-c").glob("*.json")
    )
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in preserved}
    captured: list[str] = []
    real_capture = evaluation_capture.capture_stage

    def tracked_capture(*args: Any, **kwargs: Any) -> dict[str, Any]:
        captured.append(str(kwargs["kind"]))
        return real_capture(*args, **kwargs)

    monkeypatch.setattr(phase2ec_runner, "capture_stage", tracked_capture)
    provider = TrackingFixture()
    outputs = run_four_stage(provider, evidence_dir=evidence)

    assert captured == list(phase2ec_runner.STAGES) == provider.calls
    assert list(outputs) == list(phase2ec_runner.STAGES)
    assert sorted(path.name for path in evidence.glob("*.json")) == [
        f"{stage}.json" for stage in sorted(phase2ec_runner.STAGES)
    ]
    assert all(
        json.loads((evidence / f"{stage}.json").read_text())["raw_output"]
        for stage in phase2ec_runner.STAGES
    )
    assert before == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in preserved}

    with pytest.raises(PreflightError, match="retry_evidence_exists"):
        run_four_stage(TrackingFixture(), evidence_dir=evidence)


def test_failed_stage_stops_downstream_execution(tmp_path: Path) -> None:
    evidence = tmp_path / "run-a-retry"
    provider = TrackingFixture(fail_at=2)
    with pytest.raises(EvaluationStopped, match="provider_failed"):
        run_four_stage(provider, evidence_dir=evidence)
    assert provider.calls == ["brief_analysis", "creative_strategy"]
    assert (evidence / "brief_analysis.json").is_file()
    failed = json.loads((evidence / "creative_strategy.json").read_text())
    assert failed["evaluation_status"] == "provider_failed" and failed["evaluated"] is False
    assert not (evidence / "content_plan.json").exists()
    assert not (evidence / "copywriting.json").exists()
