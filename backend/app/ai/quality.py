"""Conservative claim checks for creative output, grounded in the approved brief.

This is a narrow lexical guard. A clear result is not proof of semantic grounding.
"""

import re
from typing import Any

VERSION = "claim-rules-v2"
CLAIM_CLASSES = (
    "confirmed_brief_fact",
    "unsupported_product_claim",
    "audience_hypothesis",
    "creative_proposal",
    "operational_assumption",
)

# Deliberately small: extend with reviewed cases, not an unbounded word blacklist.
VARIETIES = re.compile(r"\b(?:apples?|pears?|berries|berry|oranges?|bananas?|grapes?|strawberries)\b", re.I)
FRESHNESS = re.compile(
    r"\bfarm[ -]?fresh\b|\bfreshly[ -]?(?:picked|harvested)\b|"
    r"\bfresh\b[ -]+(?:seasonal[ -]+)?(?:fruit|apples?|pears?|berries|produce|box)\b|"
    r"\b(?:fruit|apples?|pears?|berries|produce|box)\b[ -]+(?:is|are|stays?)[ -]+fresh\b",
    re.I,
)
PROVENANCE = re.compile(r"\b(?:locally grown|farm grown|grown locally|harvested at|harvested from)\b", re.I)
HARVEST_HINT = re.compile(r"\b(?:harvest journey|autumn harvest|from orchard to table)\b", re.I)
DESTINATION = re.compile(r"\b(?:link in (?:our |the |your )?bio|single[ -]?click (?:sign[ -]?up|waitlist))\b", re.I)
SENSORY_ATTRIBUTE = re.compile(
    r"\b(?:crisp bite|juicy (?:fruit|produce)|sweet (?:fruit|produce)|"
    r"tart (?:fruit|produce)|ripe (?:fruit|produce)|rich flavor|bursting with flavor)\b",
    re.I,
)
SIGNUP_MECHANISM = re.compile(
    r"\b(?:sign[ -]?up form|waitlist form|form with fields?|fields? for (?:name|email)|"
    r"enter (?:your )?email|submit the form)\b",
    re.I,
)
PRIORITY_PROMISE = re.compile(
    r"\b(?:be the first to hear|first access|priority access|early access)\b", re.I
)
ASSET_ASSERTION = re.compile(
    r"\b(?:provided|existing|available|approved|client[ -]?supplied) "
    r"(?:photo|image|asset|footage|video|media)\b",
    re.I,
)
PROPOSAL_MARKER = re.compile(
    r"\b(?:proposed|concept|could use|would use|asset requirement|"
    r"if available|subject to availability|no actual (?:asset|media))\b",
    re.I,
)
HYPOTHESIS_MARKER = re.compile(
    r"\b(?:likely|may|might|could|hypothesis|assumption|potentially|we expect)\b", re.I
)
CLAIM_PATTERNS = {
    "price": re.compile(r"(?:[$€£]\s*\d|\b\d+\s*(?:dollars|USD)\b|\bpriced at\b|\b\d+%\s*(?:off|discount)\b)", re.I),
    "delivery": re.compile(r"\b(?:delivered? (?:on|by|to)|ships? (?:on|to|within)|arrives? by|guaranteed delivery)\b", re.I),
    "nutrition": re.compile(r"\b(?:rich in (?:vitamins?|nutrients?)|high in (?:vitamins?|fiber)|low sugar|nutritious|healthy)\b", re.I),
    "certification": re.compile(r"\b(?:certified organic|USDA organic|fair trade certified|non-GMO certified)\b", re.I),
    "stock": re.compile(r"\b(?:in stock|limited stock|available now|only \d+ (?:boxes|left)|selling out)\b", re.I),
    "testimonial": re.compile(r"\b(?:customers? (?:say|love)|five[ -]?star|rated \d|reviewers? say)\b", re.I),
}


def _plain(text: str) -> str:
    # Hashtags are visible copy: split common camel-case forms before matching.
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).replace("#", "")


def _facts(brief: dict[str, Any]) -> str:
    return " ".join(
        str(brief.get(key) or "")
        for key in ("objective", "target_audience", "key_message", "content_type", "additional_context")
    )


def _supported(phrase: str, facts: str) -> bool:
    for sentence in re.split(r"[.!?;\n]", facts):
        if re.search(r"\b" + re.escape(phrase) + r"\b", sentence, re.I) and not re.search(
            r"\b(?:no|not|without|avoid|do not|unknown|unconfirmed)\b", sentence, re.I
        ):
            return True
    return False


def _fields(kind: str, output: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []

    def add(prefix: str, value: dict[str, Any], names: tuple[str, ...]) -> None:
        for name in names:
            item = value.get(name)
            if isinstance(item, str):
                fields.append((prefix + name, item))
            elif isinstance(item, list):
                fields.extend((f"{prefix}{name}[{i}]", v) for i, v in enumerate(item) if isinstance(v, str))

    if kind == "brief_analysis":
        add("", output, ("objective_summary", "key_themes", "content_pillars"))
        add("target_audience.", output.get("target_audience") or {}, ("description", "primary_needs"))
    elif kind == "creative_strategy":
        for i, item in enumerate(output.get("creative_directions") or []):
            add(f"creative_directions[{i}].", item, ("concept_name", "strategic_rationale", "key_message", "audience_insight", "tone_of_voice", "visual_direction"))
    elif kind == "content_plan":
        for i, item in enumerate(output.get("content_plan") or []):
            add(f"content_plan[{i}].", item, ("title", "content_pillar", "content_format", "objective", "key_message", "draft_caption", "visual_direction", "call_to_action"))
    elif kind == "copywriting":
        add("", output, ("headline", "caption", "call_to_action", "hashtags", "revision_notes"))
    return fields


def assess(kind: str, output: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    """Return separate findings; never modify or reject the model output itself."""
    facts = _facts(brief)
    restrictions = str(brief.get("restrictions") or "")
    explicitly_restricted = bool(re.search(r"\b(?:do not|avoid|never)\b", restrictions, re.I))
    findings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(code: str, severity: str, claim_class: str, field: str, excerpt: str) -> None:
        if (code, field) not in seen:
            findings.append({"code": code, "severity": severity, "claim_class": claim_class, "field": field, "excerpt": excerpt[:200]})
            seen.add((code, field))

    for field, raw in _fields(kind, output):
        text = _plain(raw)
        # Revision notes describe work, not client-facing claims. Check false
        # compliance assertions below after the visible text has been scanned.
        if field.startswith("revision_notes["):
            continue
        for variety_match in VARIETIES.finditer(text):
            term = variety_match.group().lower()
            singular = {"berries": "berry", "apples": "apple", "pears": "pear", "oranges": "orange", "bananas": "banana", "grapes": "grape", "strawberries": "strawberry"}.get(term, term)
            varieties_forbidden = explicitly_restricted and bool(re.search(r"\b(?:fruit variet(?:y|ies)|exact variet(?:y|ies))\b", restrictions, re.I))
            if varieties_forbidden or not _supported(term, facts) and not _supported(singular, facts):
                add("unconfirmed_fruit_variety", "critical", "unsupported_product_claim", field, raw)
        if re.search(r"\bfarm[ -]?fresh\b", text, re.I) and not _supported("farm fresh", facts):
            add("unconfirmed_provenance", "critical", "unsupported_product_claim", field, raw)
        confirmed_freshness = any(_supported(phrase, facts) for phrase in (
            "farm fresh", "fresh fruit", "fresh produce", "fresh box", "fresh apples",
            "fresh pears", "fresh berries", "freshly picked", "freshly harvested",
            "fruit is fresh", "fruit are fresh",
        ))
        if FRESHNESS.search(text) and not confirmed_freshness:
            add("unconfirmed_freshness", "critical", "unsupported_product_claim", field, raw)
        if PROVENANCE.search(text) and not any(_supported(p, facts) for p in ("locally grown", "farm grown", "harvested")):
            add("unconfirmed_provenance", "critical", "unsupported_product_claim", field, raw)
        if HARVEST_HINT.search(text) and not _supported("harvest", facts):
            add("possible_provenance", "review", "creative_proposal", field, raw)
        if DESTINATION.search(text) and not _supported("link in bio", facts) and not _supported("single-click", facts):
            add("unconfirmed_signup_destination", "review", "operational_assumption", field, raw)
        sensory_match = SENSORY_ATTRIBUTE.search(text)
        if sensory_match and not _supported(sensory_match.group(), facts):
            add("unconfirmed_sensory_attribute", "critical", "unsupported_product_claim", field, raw)
        if SIGNUP_MECHANISM.search(text):
            add("unconfirmed_signup_mechanism", "review", "operational_assumption", field, raw)
        if PRIORITY_PROMISE.search(text):
            add("unconfirmed_notification_priority", "review", "operational_assumption", field, raw)
        if ASSET_ASSERTION.search(text) and not PROPOSAL_MARKER.search(text):
            add("unconfirmed_asset_provenance", "review", "operational_assumption", field, raw)
        for code, pattern in CLAIM_PATTERNS.items():
            match = pattern.search(text)
            if match and not _supported(match.group(), facts):
                add("unconfirmed_" + code, "critical", "unsupported_product_claim", field, raw)
        if ("audience_insight" in field or "primary_needs" in field) and re.search(
            r"\b(?:look for|appreciate|browse|prefer|want|need|discover)\b", text, re.I
        ) and raw not in facts and not HYPOTHESIS_MARKER.search(text):
            add("audience_hypothesis", "review", "audience_hypothesis", field, raw)

    if kind == "copywriting" and any(f["severity"] == "critical" for f in findings):
        for field, raw in _fields(kind, output):
            if field.startswith("revision_notes[") and re.search(r"\b(?:maintained|respected|complied with)\b.{0,40}\b(?:restriction|guideline|language)\b", raw, re.I):
                add("unverified_compliance_note", "review", "operational_assumption", field, raw)

    disposition = "critical" if any(f["severity"] == "critical" for f in findings) else "review" if findings else "clear"
    return {"version": VERSION, "disposition": disposition, "findings": findings, "scope": "known lexical claims only; human review remains required"}
