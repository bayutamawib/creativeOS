"""Offline checks for prompt selection and copy evaluation semantics."""

import json
import os
from pathlib import Path

import pytest

from app.ai import evaluation, providers
from app.ai.contracts import (
    PROMPT_VERSION,
    PROMPTS_V1,
    REPORT_PROMPT_VERSION,
    GenerationFailure,
    prompt_for,
    validate,
)
from app.ai.providers import adapter
from app.ai.quality import assess as claim_assess
from app.config import settings


def test_creative_v2_prompts_and_v1_replay():
    assert PROMPT_VERSION == "creative-v5" and REPORT_PROMPT_VERSION == "creative-v1"
    assert prompt_for("copywriting", "creative-v1") == PROMPTS_V1["copywriting"]
    assert "audience" in prompt_for("brief_analysis", PROMPT_VERSION)
    assert "editorial themes" in prompt_for("brief_analysis", PROMPT_VERSION)
    assert "substantively different" in prompt_for("creative_strategy", PROMPT_VERSION)
    assert "requested formats" in prompt_for("content_plan", PROMPT_VERSION)
    assert "destination-neutral" in prompt_for("copywriting", PROMPT_VERSION)
    assert "one structured copy suggestion" in prompt_for("copywriting", PROMPT_VERSION)
    assert "variants" not in prompt_for("copywriting", PROMPT_VERSION)
    assert adapter("fixture", "creative-v1") and adapter("fixture", "creative-v2")
    assert adapter("fixture", "creative-v3") and adapter("fixture", "creative-v4")
    assert adapter("fixture", "creative-v5")
    with pytest.raises(GenerationFailure, match="unsupported_prompt_version"):
        adapter("fixture", "creative-v6")


def test_compatible_adapter_uses_job_prompt_version_without_network(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "compatible")
    monkeypatch.setenv("AI_ENDPOINT", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("AI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("APP_DB_PASSWORD", "synthetic-test-password")
    settings.cache_clear()
    requests = []

    class Result:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, *_args):
            return b'{"choices":[{"message":{"content":"{}"}}]}'

    class Opener:
        def open(self, request, **_kwargs):
            requests.append(json.loads(request.data))
            return Result()

    monkeypatch.setattr(providers, "build_opener", lambda *_args: Opener())
    for version in ("creative-v1", "creative-v2"):
        provider = adapter("compatible", version)
        provider.generate("copywriting", "synthetic-model", {}, {"temperature": 0.5, "max_output_tokens": 128})
    assert len(requests) == 2
    for request, version in zip(requests, ("creative-v1", "creative-v2"), strict=True):
        assert prompt_for("copywriting", version) in request["messages"][0]["content"]
    assert requests[0]["messages"][0]["content"] != requests[1]["messages"][0]["content"]


def test_copy_grounding_is_independent_of_verbatim_reuse():
    ctx = {"brief": {"objective": "Invite home cooks to a waitlist."}, "plan_item": {
        "title": "Waitlist", "draft_caption": "Join the waitlist.", "call_to_action": "Join the waitlist."
    }}
    reused = {"headline": "Waitlist", "caption": "Join the waitlist.",
              "call_to_action": "Join the waitlist.", "hashtags": [], "revision_notes": [],
              "potential_risks": []}
    assert evaluation.assess("copywriting", reused, ctx)
    no_change = evaluation.copy_review(reused, ctx, "Improve the caption and CTA")
    assert no_change["verbatim_caption_and_cta"]
    assert no_change["editorial_review_required"]
    preserved = evaluation.copy_review(reused, ctx, "Preserve the caption and CTA verbatim")
    assert preserved["preservation_requested"] and not preserved["editorial_review_required"]
    rejected_preservation = evaluation.copy_review(reused, ctx, "Do not preserve; improve the caption")
    assert not rejected_preservation["preservation_requested"] and rejected_preservation["editorial_review_required"]
    revised = reused | {"caption": "A seasonal invitation for home cooks. Join the waitlist."}
    assert evaluation.assess("copywriting", revised, ctx)
    assert evaluation.copy_review(revised, ctx, "Improve the caption")["editorial_change_detected"]
    unsupported = reused | {"hashtags": ["#FarmFresh"]}
    assert not evaluation.assess("copywriting", unsupported, ctx)
    assert evaluation.copy_review(unsupported | {"revision_notes": ["Maintained restricted language."]}, ctx)["editorial_review_required"]
    accurate = revised | {"revision_notes": ["Revised the caption for clarity."]}
    assert evaluation.copy_review(accurate, ctx, "Revise the caption")["revision_notes_accurate_on_checkable_claims"]


def test_direction_duplicate_review_is_separate_from_creativity():
    base = {"strategic_rationale": "Focus on recipe ideas.", "audience_insight": "Home cooks may want inspiration."}
    repeated = {"creative_directions": [base, base | {"concept_name": "Different title"}]}
    distinct = {"creative_directions": [base, base | {"strategic_rationale": "Focus on fruit textures."}]}
    assert evaluation.direction_review(repeated)["distinctiveness_review_required"]
    assert not evaluation.direction_review(distinct)["distinctiveness_review_required"]


def test_historical_synthetic_evidence_can_be_replayed_offline():
    root = Path(os.environ.get("CREATIVE_QUALITY_EVIDENCE_DIR") or (
        Path(__file__).resolve().parents[2] / "creativeOS-uat-evidence" / "phase2c"
    ))
    expected = {
        "brief_analysis.json": "critical", "creative_strategy.json": "review",
        "content_plan.json": "critical", "copywriting.json": "critical",
    }
    if not all((root / name).is_file() for name in expected):
        pytest.skip("Local sanitized UAT evidence is not packaged with the repository")
    for name, disposition in expected.items():
        evidence = json.loads((root / name).read_text())
        result = claim_assess(evidence["stage"], evidence["output_redacted"], evidence["input_redacted"]["brief"])
        assert result["disposition"] == disposition
        if name == "content_plan.json":
            validate("content_plan", json.dumps(evidence["output_redacted"]), {
                "target_count": 3, "channels": ["Instagram", "Website"]
            })
            with pytest.raises(GenerationFailure, match="invalid_plan"):
                validate("content_plan", json.dumps(evidence["output_redacted"]), {
                    "target_count": 2, "channels": ["Instagram", "Website"]
                })
    copy = json.loads((root / "copywriting.json").read_text())
    comparison = evaluation.copy_review(copy["output_redacted"], copy["input_redacted"])
    assert comparison["verbatim_caption_and_cta"]
    assert not comparison["editorial_change_detected"]
    assert not comparison["revision_notes_accurate_on_checkable_claims"]
