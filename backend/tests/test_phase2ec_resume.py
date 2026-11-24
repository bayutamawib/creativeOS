import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.ai import evaluation_capture, phase2ec_runner
from app.ai.contracts import GenerationFailure
from app.ai.evaluation_capture import EvaluationStopped
from app.ai.phase2ec_runner import PreflightError, resume_stage_two
from app.ai.providers import Fixture, Response


class ResumeProvider(Fixture):
    prompt_version = "creative-v2"

    def __init__(self, mode: str = "success"):
        self.mode = mode
        self.calls: list[str] = []

    def generate(
        self,
        kind: str,
        model: str,
        context: dict[str, Any],
        params: dict[str, Any],
    ) -> Response:
        self.calls.append(kind)
        if self.mode == "provider":
            raise GenerationFailure("provider_unavailable", True)
        if self.mode == "validation":
            return Response("{}", 10, 5)
        return super().generate(kind, model, context, params)


def _resume_dir(tmp_path: Path) -> tuple[Path, bytes]:
    evidence = tmp_path / "run-a-retry"
    evidence.mkdir(parents=True)
    source = phase2ec_runner.RETRY_DIR / "brief_analysis.json"
    target = evidence / "brief_analysis.json"
    shutil.copyfile(source, target)
    return evidence, target.read_bytes()


def _rewrite_stage_one(
    evidence: Path, monkeypatch: pytest.MonkeyPatch, update: dict[str, Any]
) -> None:
    path = evidence / "brief_analysis.json"
    record = json.loads(path.read_text())
    record.update(update)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    monkeypatch.setattr(
        phase2ec_runner,
        "STAGE1_CHECKPOINT",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_successful_stage_two_resume_preserves_stage_one(tmp_path: Path) -> None:
    evidence, stage_one_before = _resume_dir(tmp_path)
    provider = ResumeProvider()

    output = resume_stage_two(provider, evidence_dir=evidence)

    assert provider.calls == ["creative_strategy"]
    assert "creative_directions" in output
    assert (evidence / "brief_analysis.json").read_bytes() == stage_one_before
    stage_two = json.loads((evidence / "creative_strategy.json").read_text())
    assert stage_two["stage"] == "creative_strategy"
    assert stage_two["provider"] == "groq"
    assert stage_two["prompt_version"] == "creative-v2"
    assert stage_two["evaluation_status"] == "evaluated"
    assert set(path.name for path in evidence.iterdir()) == {
        "brief_analysis.json",
        "creative_strategy.json",
    }


def test_stage_one_hash_mismatch_stops_before_provider(tmp_path: Path) -> None:
    evidence, _ = _resume_dir(tmp_path)
    path = evidence / "brief_analysis.json"
    path.write_bytes(path.read_bytes() + b"\n")
    provider = ResumeProvider()
    with pytest.raises(PreflightError, match="stage1_checkpoint_mismatch"):
        resume_stage_two(provider, evidence_dir=evidence)
    assert provider.calls == []


@pytest.mark.parametrize(
    ("update", "error"),
    [
        ({"validation_outcome": "failed"}, "stage1_invalid_status"),
        (
            {
                "claim_check": {
                    "findings": [{"severity": "critical", "code": "synthetic"}]
                }
            },
            "stage1_invalid_claim_status",
        ),
        ({"output": {"objective_summary": "changed"}}, "stage1_output_mismatch"),
    ],
)
def test_invalid_stage_one_status_stops_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    update: dict[str, Any],
    error: str,
) -> None:
    evidence, _ = _resume_dir(tmp_path)
    _rewrite_stage_one(evidence, monkeypatch, update)
    provider = ResumeProvider()
    with pytest.raises(PreflightError, match=error):
        resume_stage_two(provider, evidence_dir=evidence)
    assert provider.calls == []


def test_existing_stage_two_and_unexpected_artifacts_are_rejected(tmp_path: Path) -> None:
    evidence, _ = _resume_dir(tmp_path)
    (evidence / "creative_strategy.json").write_text("{}")
    with pytest.raises(PreflightError, match="stage2_evidence_exists"):
        resume_stage_two(ResumeProvider(), evidence_dir=evidence)

    evidence, _ = _resume_dir(tmp_path / "other")
    (evidence / "unexpected.json").write_text("{}")
    with pytest.raises(PreflightError, match="unexpected_retry_evidence"):
        resume_stage_two(ResumeProvider(), evidence_dir=evidence)


@pytest.mark.parametrize(
    ("mode", "category"),
    [
        ("provider", "provider_failed"),
        ("capture", "capture_failed"),
        ("validation", "validation_failed"),
        ("claim", "claim_check_failed"),
    ],
)
def test_stage_two_failures_are_classified_and_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    category: str,
) -> None:
    evidence, stage_one_before = _resume_dir(tmp_path)
    provider = ResumeProvider(mode)
    if mode == "capture":
        monkeypatch.setattr(
            evaluation_capture,
            "_persist",
            lambda *_args: (_ for _ in ()).throw(OSError("synthetic capture failure")),
        )
    elif mode == "claim":
        monkeypatch.setattr(
            evaluation_capture,
            "assess",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic claim failure")),
        )

    with pytest.raises(EvaluationStopped) as stopped:
        resume_stage_two(provider, evidence_dir=evidence)

    assert stopped.value.category == category
    assert stopped.value.record["evaluation_status"] == category
    assert stopped.value.record["evaluated"] is False
    assert provider.calls == ["creative_strategy"]
    assert (evidence / "brief_analysis.json").read_bytes() == stage_one_before
    assert not (evidence / "content_plan.json").exists()
    assert not (evidence / "copywriting.json").exists()
