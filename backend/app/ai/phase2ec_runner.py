"""Bounded four-stage Phase 2E-C Run A evaluator."""

import hashlib
import json
from pathlib import Path
from typing import Any

from app.ai.contracts import (
    PROMPT_VERSION,
    TEMPERATURES,
    GenerationFailure,
    strict_json_loads,
    validate,
)
from app.ai.evaluation_capture import capture_stage
from app.ai.providers import Compatible, Provider
from app.ai.quality import assess

MODEL = "openai/gpt-oss-20b"
STAGES = ("brief_analysis", "creative_strategy", "content_plan", "copywriting")
REPOSITORY = Path(__file__).resolve().parents[3]
BASELINE_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2c"
RETRY_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "run-a-retry"
RUN_B_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "run-b"
RUN_C_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "run-c"
STAGE3_HANDOFF = (
    REPOSITORY
    / "creativeOS-uat-evidence"
    / "phase2e-c"
    / "stage3-handoff"
    / "proposed_strategy_handoff.json"
)
STAGE3_APPROVAL = STAGE3_HANDOFF.parent / "owner_approval.json"
STAGE3_RUN_A_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "stage3-run-a"
STAGE4_HANDOFF = (
    REPOSITORY
    / "creativeOS-uat-evidence"
    / "phase2e-c"
    / "stage4-handoff"
    / "proposed_content_plan_handoff.json"
)
STAGE4_APPROVAL = STAGE4_HANDOFF.parent / "owner_approval.json"
STAGE4_RUN_A_DIR = REPOSITORY / "creativeOS-uat-evidence" / "phase2e-c" / "stage4-run-a"
STAGE1_CHECKPOINT = "adb72931044d12b169de057f9b4ed0bbc66526a5a29b8759b21860117bf6416d"
HISTORICAL_STAGE2_CHECKPOINT = "64e1fc261e5f147735ac5e9f62fc7e345a39981e8dec4b957816d74e6fe0766b"
RUN_B_CHECKPOINT = "c2e0fa9110294bff6e3909bcf9f413270c947760ec0c9acbcb3f50801ca08792"
RUN_C_CHECKPOINT = "5499db92b32599719625d7e351db14efd8be8ce857a656016c329f368b781efa"
STAGE3_RUN_A_CHECKPOINT = "143df5b114ccb5cae99ec22ab9390ce2a5f5d3ef013f7b982c7b058ac97b0090"
STAGE4_HANDOFF_CHECKPOINT = "69f96a0a1bfab6ccf21ba5507989611103e89145d3772785be37a07a4b016104"
OUTPUT_LIMITS = {
    "brief_analysis": 1200,
    "creative_strategy": 1500,
    "content_plan": 1800,
    "copywriting": 1500,
}


class PreflightError(Exception):
    """Run A cannot safely start without overwriting or changing provenance."""


def _load_baseline(path: Path) -> dict[str, dict[str, Any]]:
    return {stage: json.loads((path / f"{stage}.json").read_text()) for stage in STAGES}


def run_four_stage(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    evidence_dir: Path = RETRY_DIR,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, dict[str, Any]]:
    """Run each stage once; any failed stage stops downstream execution."""
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise PreflightError("retry_evidence_exists")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")

    baseline = _load_baseline(baseline_dir)
    brief = baseline["brief_analysis"]["input_redacted"]["brief"]
    brand = baseline["brief_analysis"]["input_redacted"]["brand"]
    channels = baseline["brief_analysis"]["parameters_redacted"]["channels"]
    target_count = baseline["brief_analysis"]["parameters_redacted"]["target_count"]
    outputs: dict[str, dict[str, Any]] = {}

    for stage in STAGES:
        context: dict[str, Any] = {"brand": brand, "brief": brief, "attachments": []}
        if stage == "creative_strategy":
            context["analysis"] = outputs["brief_analysis"]
        elif stage == "content_plan":
            context["direction"] = outputs["creative_strategy"]["creative_directions"][0]
        elif stage == "copywriting":
            item = outputs["content_plan"]["content_plan"][0]
            context.update(
                direction=outputs["creative_strategy"]["creative_directions"][0],
                plan_item=item,
                revision=item,
            )
        params: dict[str, Any] = {
            "include": [],
            "channels": channels,
            "feedback": None,
            "temperature": TEMPERATURES[stage],
            "max_output_tokens": OUTPUT_LIMITS[stage],
        }
        if stage == "content_plan":
            params["target_count"] = target_count
        outputs[stage] = capture_stage(
            provider,
            provider_name="groq",
            kind=stage,
            model=MODEL,
            prompt_version=prompt_version,
            context=context,
            params=params,
            evidence_path=evidence_dir / f"{stage}.json",
        )
    return outputs


def _validated_stage_one(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != STAGE1_CHECKPOINT:
        raise PreflightError("stage1_checkpoint_mismatch")
    try:
        record = json.loads(raw_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError("stage1_invalid_evidence") from exc
    if (
        record.get("evaluation_status") != "evaluated"
        or record.get("evaluated") is not True
        or record.get("validation_outcome") != "passed"
        or record.get("prompt_version") != PROMPT_VERSION
        or record.get("model") != MODEL
        or record.get("provider") != "groq"
    ):
        raise PreflightError("stage1_invalid_status")
    raw_output = record.get("raw_output")
    output = record.get("output")
    if not isinstance(raw_output, str) or not isinstance(output, dict):
        raise PreflightError("stage1_missing_output")
    findings = record.get("claim_check", {}).get("findings")
    if not isinstance(findings, list) or any(
        isinstance(finding, dict) and finding.get("severity") == "critical"
        for finding in findings
    ):
        raise PreflightError("stage1_invalid_claim_status")
    try:
        revalidated = validate("brief_analysis", raw_output, {})
    except GenerationFailure as exc:
        raise PreflightError("stage1_revalidation_failed") from exc
    if revalidated != output:
        raise PreflightError("stage1_output_mismatch")
    return output


def resume_stage_two(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    evidence_dir: Path = RETRY_DIR,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    """Resume only Creative Strategist from the owner-approved Stage 1 checkpoint."""
    stage_one_path = evidence_dir / "brief_analysis.json"
    stage_two_path = evidence_dir / "creative_strategy.json"
    if not stage_one_path.is_file():
        raise PreflightError("stage1_evidence_missing")
    if stage_two_path.exists():
        raise PreflightError("stage2_evidence_exists")
    artifacts = {path.name for path in evidence_dir.iterdir()}
    if artifacts != {stage_one_path.name}:
        raise PreflightError("unexpected_retry_evidence")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")

    analysis = _validated_stage_one(stage_one_path)
    baseline = _load_baseline(baseline_dir)
    source = baseline["brief_analysis"]
    context = {
        "brand": source["input_redacted"]["brand"],
        "brief": source["input_redacted"]["brief"],
        "analysis": analysis,
        "attachments": [],
    }
    params = {
        "include": [],
        "channels": source["parameters_redacted"]["channels"],
        "feedback": None,
        "temperature": TEMPERATURES["creative_strategy"],
        "max_output_tokens": OUTPUT_LIMITS["creative_strategy"],
    }
    return capture_stage(
        provider,
        provider_name="groq",
        kind="creative_strategy",
        model=MODEL,
        prompt_version=prompt_version,
        context=context,
        params=params,
        evidence_path=stage_two_path,
    )


def run_stage_two_b(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    source_stage_one: Path = RETRY_DIR / "brief_analysis.json",
    historical_stage_two: Path = RETRY_DIR / "creative_strategy.json",
    evidence_dir: Path = RUN_B_DIR,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    """Run only Stage 2 using immutable Run A Retry evidence as provenance."""
    stage_two_path = evidence_dir / "creative_strategy.json"
    if stage_two_path.exists():
        raise PreflightError("stage2_evidence_exists")
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise PreflightError("unexpected_run_b_evidence")
    if not source_stage_one.is_file():
        raise PreflightError("stage1_evidence_missing")
    if not historical_stage_two.is_file():
        raise PreflightError("historical_stage2_evidence_missing")
    if hashlib.sha256(historical_stage_two.read_bytes()).hexdigest() != HISTORICAL_STAGE2_CHECKPOINT:
        raise PreflightError("historical_stage2_checkpoint_mismatch")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")

    analysis = _validated_stage_one(source_stage_one)
    baseline = _load_baseline(baseline_dir)
    source = baseline["brief_analysis"]
    context = {
        "brand": source["input_redacted"]["brand"],
        "brief": source["input_redacted"]["brief"],
        "analysis": analysis,
        "attachments": [],
    }
    params = {
        "include": [],
        "channels": source["parameters_redacted"]["channels"],
        "feedback": None,
        "temperature": TEMPERATURES["creative_strategy"],
        "max_output_tokens": OUTPUT_LIMITS["creative_strategy"],
    }
    try:
        source_path = str(source_stage_one.relative_to(REPOSITORY))
    except ValueError:
        source_path = str(source_stage_one)
    return capture_stage(
        provider,
        provider_name="groq",
        kind="creative_strategy",
        model=MODEL,
        prompt_version=prompt_version,
        context=context,
        params=params,
        evidence_path=stage_two_path,
        evidence_metadata={
            "source_stage1_evidence": source_path,
            "source_stage1_sha256": STAGE1_CHECKPOINT,
            "provider": "groq",
            "model": MODEL,
            "prompt_version": prompt_version,
        },
    )


def run_stage_two_c(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    source_stage_one: Path = RETRY_DIR / "brief_analysis.json",
    source_run_b: Path = RUN_B_DIR / "creative_strategy.json",
    evidence_dir: Path = RUN_C_DIR,
    prompt_version: str = "creative-v3",
) -> dict[str, Any]:
    """Run only Stage 2 with v3 after verifying Stage 1 and Run B provenance."""
    stage_two_path = evidence_dir / "creative_strategy.json"
    if stage_two_path.exists():
        raise PreflightError("stage2_evidence_exists")
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise PreflightError("unexpected_run_c_evidence")
    if not source_stage_one.is_file():
        raise PreflightError("stage1_evidence_missing")
    if not source_run_b.is_file():
        raise PreflightError("run_b_evidence_missing")
    if hashlib.sha256(source_run_b.read_bytes()).hexdigest() != RUN_B_CHECKPOINT:
        raise PreflightError("run_b_checkpoint_mismatch")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")

    analysis = _validated_stage_one(source_stage_one)
    baseline = _load_baseline(baseline_dir)
    source = baseline["brief_analysis"]
    context = {
        "brand": source["input_redacted"]["brand"],
        "brief": source["input_redacted"]["brief"],
        "analysis": analysis,
        "attachments": [],
    }
    params = {
        "include": [],
        "channels": source["parameters_redacted"]["channels"],
        "feedback": None,
        "temperature": TEMPERATURES["creative_strategy"],
        "max_output_tokens": OUTPUT_LIMITS["creative_strategy"],
    }
    try:
        stage_one_path = str(source_stage_one.relative_to(REPOSITORY))
        run_b_path = str(source_run_b.relative_to(REPOSITORY))
    except ValueError:
        stage_one_path = str(source_stage_one)
        run_b_path = str(source_run_b)
    return capture_stage(
        provider,
        provider_name="groq",
        kind="creative_strategy",
        model=MODEL,
        prompt_version=prompt_version,
        context=context,
        params=params,
        evidence_path=stage_two_path,
        evidence_metadata={
            "source_stage1_evidence": stage_one_path,
            "source_stage1_sha256": STAGE1_CHECKPOINT,
            "prior_stage2_evidence": run_b_path,
            "prior_stage2_sha256": RUN_B_CHECKPOINT,
            "provider": "groq",
            "model": MODEL,
            "prompt_version": prompt_version,
        },
    )


def load_approved_stage3_handoff(
    path: Path = STAGE3_HANDOFF,
    *,
    baseline_dir: Path = BASELINE_DIR,
    source_run_c: Path = RUN_C_DIR / "creative_strategy.json",
    approval_path: Path | None = None,
) -> dict[str, Any]:
    """Load a human handoff only after explicit owner approval and safety checks."""
    if not path.is_file():
        raise PreflightError("stage3_handoff_missing")
    if not source_run_c.is_file() or hashlib.sha256(source_run_c.read_bytes()).hexdigest() != RUN_C_CHECKPOINT:
        raise PreflightError("run_c_checkpoint_mismatch")
    try:
        artifact = strict_json_loads(path.read_text())
    except GenerationFailure as exc:
        raise PreflightError("stage3_handoff_invalid_json") from exc
    if not isinstance(artifact, dict):
        raise PreflightError("stage3_handoff_invalid")
    if (
        artifact.get("artifact_type") != "human_reviewed_stage2_handoff_proposal"
        or artifact.get("model_generated") is not False
        or artifact.get("source_stage2_editorial_acceptance") != "failed"
        or artifact.get("source_stage2_sha256") != RUN_C_CHECKPOINT
    ):
        raise PreflightError("stage3_handoff_invalid_provenance")
    embedded_approval = (
        artifact.get("human_review_status") == "owner_approved"
        and artifact.get("downstream_execution_authorized") is True
    )
    if not embedded_approval:
        if approval_path is None or not approval_path.is_file():
            raise PreflightError("stage3_owner_approval_required")
        try:
            approval = strict_json_loads(approval_path.read_text())
        except GenerationFailure as exc:
            raise PreflightError("stage3_approval_invalid_json") from exc
        if not isinstance(approval, dict):
            raise PreflightError("stage3_approval_invalid")
        try:
            proposal_path = str(path.relative_to(REPOSITORY))
        except ValueError:
            proposal_path = str(path)
        if (
            approval.get("record_type") != "owner_approval"
            or approval.get("approval_status") != "owner_approved"
            or approval.get("approval_scope") != "stage3_content_planner_evaluation_only"
            or approval.get("approved_proposal_evidence") != proposal_path
            or approval.get("approved_proposal_sha256")
            != hashlib.sha256(path.read_bytes()).hexdigest()
            or approval.get("source_stage2_sha256") != RUN_C_CHECKPOINT
            or approval.get("source_stage2_editorial_acceptance") != "failed"
            or approval.get("stage2_model_performance_reclassified") is not False
            or approval.get("stage4_execution_authorized") is not False
        ):
            raise PreflightError("stage3_approval_invalid")
    proposed = artifact.get("proposed_output")
    if not isinstance(proposed, dict):
        raise PreflightError("stage3_handoff_missing_output")
    try:
        output = validate("creative_strategy", json.dumps(proposed), {})
    except GenerationFailure as exc:
        raise PreflightError("stage3_handoff_invalid_output") from exc
    brief = _load_baseline(baseline_dir)["brief_analysis"]["input_redacted"]["brief"]
    if assess("creative_strategy", output, brief)["disposition"] == "critical":
        raise PreflightError("stage3_handoff_critical_findings")
    return output


def run_stage_three_a(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    handoff_path: Path = STAGE3_HANDOFF,
    approval_path: Path = STAGE3_APPROVAL,
    evidence_dir: Path = STAGE3_RUN_A_DIR,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    """Run only Content Planner from an explicitly approved human handoff."""
    evidence_path = evidence_dir / "content_plan.json"
    if evidence_path.exists():
        raise PreflightError("stage3_evidence_exists")
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise PreflightError("unexpected_stage3_evidence")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")
    strategy = load_approved_stage3_handoff(
        handoff_path,
        baseline_dir=baseline_dir,
        approval_path=approval_path,
    )
    baseline = _load_baseline(baseline_dir)
    source = baseline["brief_analysis"]
    context = {
        "brand": source["input_redacted"]["brand"],
        "brief": source["input_redacted"]["brief"],
        "direction": strategy,
        "attachments": [],
    }
    params = {
        "include": [],
        "channels": source["parameters_redacted"]["channels"],
        "feedback": None,
        "temperature": TEMPERATURES["content_plan"],
        "max_output_tokens": OUTPUT_LIMITS["content_plan"],
        "target_count": source["parameters_redacted"]["target_count"],
    }
    try:
        proposal_path = str(handoff_path.relative_to(REPOSITORY))
        approval_record_path = str(approval_path.relative_to(REPOSITORY))
    except ValueError:
        proposal_path = str(handoff_path)
        approval_record_path = str(approval_path)
    return capture_stage(
        provider,
        provider_name="groq",
        kind="content_plan",
        model=MODEL,
        prompt_version=prompt_version,
        context=context,
        params=params,
        evidence_path=evidence_path,
        evidence_metadata={
            "stage2_input_type": "human_reviewed_owner_approved_handoff",
            "stage2_model_editorial_acceptance": "failed",
            "stage2_model_performance_reclassified": False,
            "handoff_evidence": proposal_path,
            "handoff_sha256": hashlib.sha256(handoff_path.read_bytes()).hexdigest(),
            "approval_record": approval_record_path,
            "approval_record_sha256": hashlib.sha256(approval_path.read_bytes()).hexdigest(),
            "provider": "groq",
            "model": MODEL,
            "prompt_version": prompt_version,
        },
    )


def load_approved_stage4_handoff(
    path: Path = STAGE4_HANDOFF,
    *,
    source_stage3: Path = STAGE3_RUN_A_DIR / "content_plan.json",
    approval_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Load a corrected Content Plan only with a matching owner approval record."""
    if not path.is_file():
        raise PreflightError("stage4_handoff_missing")
    if (
        not source_stage3.is_file()
        or hashlib.sha256(source_stage3.read_bytes()).hexdigest() != STAGE3_RUN_A_CHECKPOINT
    ):
        raise PreflightError("stage3_checkpoint_mismatch")
    try:
        artifact = strict_json_loads(path.read_text())
    except GenerationFailure as exc:
        raise PreflightError("stage4_handoff_invalid_json") from exc
    if not isinstance(artifact, dict) or (
        artifact.get("artifact_type") != "human_reviewed_stage3_handoff_proposal"
        or artifact.get("model_generated") is not False
        or artifact.get("source_stage3_editorial_acceptance") != "failed"
        or artifact.get("source_stage3_sha256") != STAGE3_RUN_A_CHECKPOINT
    ):
        raise PreflightError("stage4_handoff_invalid_provenance")
    if approval_path is None or not approval_path.is_file():
        raise PreflightError("stage4_owner_approval_required")
    try:
        approval = strict_json_loads(approval_path.read_text())
    except GenerationFailure as exc:
        raise PreflightError("stage4_approval_invalid_json") from exc
    try:
        proposal_path = str(path.relative_to(REPOSITORY))
    except ValueError:
        proposal_path = str(path)
    if not isinstance(approval, dict) or (
        approval.get("record_type") != "owner_approval"
        or approval.get("approval_status") != "owner_approved"
        or approval.get("approval_scope") != "stage4_copywriting_evaluation_only"
        or approval.get("approved_proposal_evidence") != proposal_path
        or approval.get("approved_proposal_sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
        or approval.get("source_stage3_sha256") != STAGE3_RUN_A_CHECKPOINT
        or approval.get("source_stage3_editorial_acceptance") != "failed"
        or approval.get("stage3_model_performance_reclassified") is not False
    ):
        raise PreflightError("stage4_approval_invalid")
    proposed = artifact.get("proposed_output")
    selected = artifact.get("selected_plan_item_index")
    if not isinstance(proposed, dict) or type(selected) is not int:
        raise PreflightError("stage4_handoff_missing_output")
    try:
        output = validate(
            "content_plan",
            json.dumps(proposed),
            {"target_count": 3, "channels": ["Instagram", "Website"]},
        )
    except GenerationFailure as exc:
        raise PreflightError("stage4_handoff_invalid_output") from exc
    if assess("content_plan", output, _load_baseline(BASELINE_DIR)["brief_analysis"]["input_redacted"]["brief"])["disposition"] == "critical":
        raise PreflightError("stage4_handoff_critical_findings")
    if selected < 0 or selected >= len(output["content_plan"]):
        raise PreflightError("stage4_handoff_invalid_selection")
    return output, selected


def run_stage_four_a(
    provider: Provider,
    *,
    baseline_dir: Path = BASELINE_DIR,
    handoff_path: Path = STAGE4_HANDOFF,
    approval_path: Path = STAGE4_APPROVAL,
    evidence_dir: Path = STAGE4_RUN_A_DIR,
    prompt_version: str = PROMPT_VERSION,
) -> dict[str, Any]:
    """Run only Copywriting from an approved, corrected Content Plan handoff."""
    evidence_path = evidence_dir / "copywriting.json"
    if evidence_path.exists():
        raise PreflightError("stage4_evidence_exists")
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        raise PreflightError("unexpected_stage4_evidence")
    actual_version = getattr(provider, "prompt_version", prompt_version)
    if actual_version != prompt_version:
        raise PreflightError("provider_prompt_version_mismatch")
    plan, selected = load_approved_stage4_handoff(
        handoff_path,
        approval_path=approval_path,
    )
    baseline = _load_baseline(baseline_dir)["brief_analysis"]
    item = plan["content_plan"][selected]
    context = {
        "brand": baseline["input_redacted"]["brand"],
        "brief": baseline["input_redacted"]["brief"],
        "plan_item": item,
        "revision": item,
        "attachments": [],
    }
    params = {
        "include": [],
        "channels": baseline["parameters_redacted"]["channels"],
        "feedback": None,
        "temperature": TEMPERATURES["copywriting"],
        "max_output_tokens": OUTPUT_LIMITS["copywriting"],
    }
    return capture_stage(
        provider,
        provider_name="groq",
        kind="copywriting",
        model=MODEL,
        prompt_version=prompt_version,
        context=context,
        params=params,
        evidence_path=evidence_path,
        evidence_metadata={
            "stage3_input_type": "human_reviewed_owner_approved_handoff",
            "stage3_model_editorial_acceptance": "failed",
            "stage3_model_performance_reclassified": False,
            "handoff_sha256": hashlib.sha256(handoff_path.read_bytes()).hexdigest(),
            "approval_record_sha256": hashlib.sha256(approval_path.read_bytes()).hexdigest(),
            "selected_plan_item_index": selected,
            "provider": "groq",
            "model": MODEL,
            "prompt_version": prompt_version,
        },
    )


def main() -> None:
    run_four_stage(Compatible(PROMPT_VERSION))


if __name__ == "__main__":
    main()
