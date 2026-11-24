"""Offline checks for narrow, known Phase 2C claim failures."""

import pytest

from app.ai.quality import CLAIM_CLASSES, assess

BRIEF = {
    "objective": "Invite home cooks in Alder Vale to join the waitlist for an autumn fruit box.",
    "key_message": "Seasonal variety and simple recipe inspiration.",
    "target_audience": "Home cooks in Alder Vale.",
    "additional_context": "Fruit close-ups and recipe-card imagery are available.",
    "restrictions": "Do not claim exact fruit varieties, freshness, delivery, price, nutrition, certification, stock, or testimonials.",
}


def codes(kind, output, brief=BRIEF):
    return {f["code"]: f["severity"] for f in assess(kind, output, brief)["findings"]}


def test_claim_taxonomy_and_neutral_language():
    assert set(CLAIM_CLASSES) == {
        "confirmed_brief_fact", "unsupported_product_claim", "audience_hypothesis",
        "creative_proposal", "operational_assumption",
    }
    result = assess("copywriting", {
        "headline": "Autumn fruit box", "caption": "Explore seasonal variety and simple recipe inspiration.",
        "call_to_action": "Join the waitlist.", "hashtags": ["#SeasonalFruit"],
    }, BRIEF)
    assert result["disposition"] == "clear" and result["findings"] == []


@pytest.mark.parametrize("field,value,expected", [
    ("draft_caption", "Fresh apples, pears, and berries for your kitchen.", "unconfirmed_fruit_variety"),
    ("title", "Fresh fruit box", "unconfirmed_freshness"),
    ("call_to_action", "Tap the link in bio to join the waitlist.", "unconfirmed_signup_destination"),
    ("visual_direction", "Locally grown fruit on a table", "unconfirmed_provenance"),
    ("draft_caption", "Only 20 boxes in stock; order now.", "unconfirmed_stock"),
    ("draft_caption", "Delivered on Monday for $20.", "unconfirmed_delivery"),
    ("draft_caption", "Certified organic and high in vitamin C.", "unconfirmed_certification"),
    ("draft_caption", "Customers love our nutritious box.", "unconfirmed_testimonial"),
])
def test_plan_client_visible_fields(field, value, expected):
    item = {"title": "Autumn box", "draft_caption": "Seasonal variety", "call_to_action": "Join the waitlist"}
    item[field] = value
    assert expected in codes("content_plan", {"content_plan": [item]})


def test_copy_hashtags_and_false_compliance_note():
    result = assess("copywriting", {
        "headline": "Harvest Moments Await",
        "caption": "Swipe through the colors of fall.",
        "call_to_action": "Tap the link in bio to join the waitlist.",
        "hashtags": ["#FarmFresh"],
        "revision_notes": ["Maintained restricted language per brand guidelines."],
        "potential_risks": ["Do not claim freshness or a delivery date."],
    }, BRIEF)
    findings = {f["code"]: f for f in result["findings"]}
    assert result["disposition"] == "critical"
    assert findings["unconfirmed_freshness"]["field"] == "hashtags[0]"
    assert findings["unconfirmed_signup_destination"]["severity"] == "review"
    assert findings["unverified_compliance_note"]["severity"] == "review"
    assert "unconfirmed_delivery" not in findings  # Risk statements are not claims.


def test_source_fact_can_support_a_claim_without_upstream_ai():
    brief = BRIEF | {"objective": "Feature confirmed apples in the autumn box.", "restrictions": ""}
    assert "unconfirmed_fruit_variety" not in codes(
        "copywriting", {"caption": "Apples in the autumn box."}, brief
    )
    assert "unconfirmed_fruit_variety" in codes(
        "copywriting", {"caption": "Pears in the autumn box."}, brief
    )
    assert "unconfirmed_fruit_variety" in codes(
        "copywriting", {"caption": "Apples in the autumn box."}, BRIEF | {"objective": brief["objective"]}
    )


def test_farm_fresh_requires_farm_provenance_even_if_freshness_is_confirmed():
    brief = BRIEF | {"objective": "Feature confirmed fresh fruit.", "restrictions": ""}
    assert "unconfirmed_provenance" in codes("copywriting", {"hashtags": ["#FarmFresh"]}, brief)
    assert "unconfirmed_freshness" not in codes("copywriting", {"caption": "Fresh fruit for home cooks."}, brief)
    ideas_only = BRIEF | {"objective": "Offer fresh ideas for seasonal fruit.", "restrictions": ""}
    assert "unconfirmed_freshness" in codes("copywriting", {"caption": "Fresh fruit for home cooks."}, ideas_only)


def test_analyzer_and_strategist_ambiguous_claims_are_review_flags():
    analysis = assess("brief_analysis", {
        "objective_summary": "Invite home cooks to a waitlist.",
        "target_audience": {"description": "Home cooks in Alder Vale", "primary_needs": ["Discover fresh seasonal fruit options"]},
        "missing_information": ["Price and delivery dates are unknown"],
    }, BRIEF)
    assert analysis["disposition"] == "critical"
    assert any(f["code"] == "audience_hypothesis" for f in analysis["findings"])
    assert all("missing_information" not in f["field"] for f in analysis["findings"])
    strategy = assess("creative_strategy", {"creative_directions": [{
        "audience_insight": "Home cooks browse local produce options online.",
        "visual_direction": "Autumn harvest imagery",
    }]}, BRIEF)
    assert strategy["disposition"] == "review"
    assert {f["code"] for f in strategy["findings"]} == {"audience_hypothesis", "possible_provenance"}
