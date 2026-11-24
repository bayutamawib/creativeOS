import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from app.ai import phase2ec_runner
from app.ai.evaluation_capture import EvaluationStopped
from app.ai.phase2ec_runner import PreflightError, run_stage_two_b
from app.ai.providers import Fixture, Response


class RunBProvider(Fixture):
    prompt_version = "creative-v2"

    def __init__(self, raw: str | None = None):
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
        if self.raw is not None:
            return Response(self.raw, 120, 60)
        return super().generate(kind, model, context, params)


def _historical_hashes() -> dict[Path, str]:
    paths = (
        phase2ec_runner.RETRY_DIR / "brief_analysis.json",
        phase2ec_runner.RETRY_DIR / "creative_strategy.json",
    )
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_successful_stage_two_run_b_preserves_provenance_and_history(tmp_path: Path) -> None:
    evidence = tmp_path / "run-b"
    before = _historical_hashes()
    provider = RunBProvider()

    output = run_stage_two_b(provider, evidence_dir=evidence)

    assert provider.calls == ["creative_strategy"]
    assert "creative_directions" in output
    saved = json.loads((evidence / "creative_strategy.json").read_text())
    assert saved["evaluation_status"] == "evaluated"
    assert saved["provenance"] == {
        "source_stage1_evidence": "creativeOS-uat-evidence/phase2e-c/run-a-retry/brief_analysis.json",
        "source_stage1_sha256": phase2ec_runner.STAGE1_CHECKPOINT,
        "provider": "groq",
        "model": "openai/gpt-oss-20b",
        "prompt_version": "creative-v2",
    }
    assert before == _historical_hashes()
    assert set(path.name for path in evidence.iterdir()) == {"creative_strategy.json"}


def test_invalid_stage_one_checkpoint_stops_before_request(tmp_path: Path) -> None:
    source = tmp_path / "brief_analysis.json"
    shutil.copyfile(phase2ec_runner.RETRY_DIR / "brief_analysis.json", source)
    source.write_bytes(source.read_bytes() + b"\n")
    provider = RunBProvider()
    with pytest.raises(PreflightError, match="stage1_checkpoint_mismatch"):
        run_stage_two_b(provider, source_stage_one=source, evidence_dir=tmp_path / "run-b")
    assert provider.calls == []


def test_existing_stage_two_and_unexpected_artifacts_stop_before_request(tmp_path: Path) -> None:
    evidence = tmp_path / "run-b"
    evidence.mkdir()
    (evidence / "creative_strategy.json").write_text("{}")
    provider = RunBProvider()
    with pytest.raises(PreflightError, match="stage2_evidence_exists"):
        run_stage_two_b(provider, evidence_dir=evidence)
    assert provider.calls == []

    other = tmp_path / "other-run-b"
    other.mkdir()
    (other / "unexpected.json").write_text("{}")
    with pytest.raises(PreflightError, match="unexpected_run_b_evidence"):
        run_stage_two_b(provider, evidence_dir=other)
    assert provider.calls == []


@pytest.mark.parametrize(
    ("raw", "error_code", "error_detail"),
    [
        (
            '{"creative_directions":[],"creative_directions":[]}',
            "duplicate_json_key",
            "creative_directions",
        ),
        ("{}", "invalid_output", None),
    ],
)
def test_run_b_validation_failure_preserves_raw_and_stops(
    tmp_path: Path, raw: str, error_code: str, error_detail: str | None
) -> None:
    evidence = tmp_path / "run-b"
    before = _historical_hashes()
    provider = RunBProvider(raw)

    with pytest.raises(EvaluationStopped, match="validation_failed"):
        run_stage_two_b(provider, evidence_dir=evidence)

    saved = json.loads((evidence / "creative_strategy.json").read_text())
    assert saved["raw_output"] == raw
    assert saved["evaluation_status"] == "validation_failed"
    assert saved["validation_outcome"] == "failed"
    assert saved["evaluated"] is False
    assert saved["error_code"] == error_code
    assert saved.get("error_detail") == error_detail
    assert "claim_check" not in saved and "output" not in saved
    assert provider.calls == ["creative_strategy"]
    assert not (evidence / "content_plan.json").exists()
    assert not (evidence / "copywriting.json").exists()
    assert before == _historical_hashes()
