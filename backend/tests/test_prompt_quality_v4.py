import json

import pytest

from app.ai.contracts import GenerationFailure, PROMPT_VERSION, validate
from app.ai.providers import Fixture
from app.ai.quality import assess


def _direction(name: str) -> dict[str, object]:
    return {
        "concept_name": name,
        "strategic_rationale": "A distinct narrative proposal grounded in the approved brief.",
        "key_message": "A warm invitation to explore the fictional collection.",
        "audience_insight": "Hypothesis: home cooks may appreciate approachable seasonal inspiration.",
        "tone_of_voice": "Warm and observant",
        "visual_direction": "Proposed concept: editorial framing, soft window light, and quiet kitchen compositions; assets and rights require confirmation.",
        "suggested_channels": ["Instagram", "Website"],
        "risks": ["Review unsupported claims before release."],
    }


def test_strategy_requires_exactly_two_directions() -> None:
    two = {"creative_directions": [_direction("A"), _direction("B")]}
    assert validate("creative_strategy", json.dumps(two), {}) == two
    for count in (1, 3):
        payload = {"creative_directions": [_direction(str(i)) for i in range(count)]}
        with pytest.raises(GenerationFailure, match="invalid_output"):
            validate("creative_strategy", json.dumps(payload), {})


def test_fixture_strategy_remains_schema_valid() -> None:
    context = {"brief": {"title": "Brief", "objective": "Invite home cooks."}, "analysis": {"content_pillars": ["Inspiration"]}}
    params = {"channels": ["Instagram"], "temperature": 0.6, "max_output_tokens": 4096}
    output = json.loads(Fixture().generate("creative_strategy", "fixture-v1", context, params).content)
    assert len(validate("creative_strategy", json.dumps(output), params)["creative_directions"]) == 2
    assert PROMPT_VERSION == "creative-v5"


def test_unsupported_product_claims_remain_critical() -> None:
    output = {"creative_directions": [_direction("A"), _direction("B") | {"visual_direction": "Proposed concept featuring apples."}]}
    result = assess("creative_strategy", output, {"objective": "Invite home cooks.", "restrictions": "Do not claim fruit varieties."})
    assert result["disposition"] == "critical"
    assert any(f["code"] == "unconfirmed_fruit_variety" for f in result["findings"])
