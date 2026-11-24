from app.ai.contracts import PROMPTS_V2, PROMPTS_V4, PROMPT_VERSION, prompt_for
from app.ai.quality import assess


def test_v5_preserves_historical_prompts_and_adds_safe_visual_guidance() -> None:
    assert PROMPT_VERSION == "creative-v5"
    assert prompt_for("creative_strategy", "creative-v2") == PROMPTS_V2["creative_strategy"]
    assert "fictional art direction" in prompt_for("creative_strategy", PROMPT_VERSION)
    assert "unidentifiable shapes" in prompt_for("creative_strategy", PROMPT_VERSION)
    assert prompt_for("creative_strategy", "creative-v4") == PROMPTS_V4["creative_strategy"]


def test_freshness_and_varieties_remain_critical() -> None:
    output = {"creative_directions": [
        {"visual_direction": "Proposed scene with freshly harvested vegetables and apples."},
    ]}
    result = assess("creative_strategy", output, {"objective": "Invite home cooks."})
    codes = {finding["code"] for finding in result["findings"]}
    assert result["disposition"] == "critical"
    assert {"unconfirmed_freshness", "unconfirmed_fruit_variety"} <= codes
