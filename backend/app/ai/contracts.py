"""Versioned creative service contracts shared by both providers."""

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from app.brief_inputs import Channel

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Notes = Annotated[list[Text], Field(max_length=16)]
Nonempty = Annotated[list[Text], Field(min_length=1, max_length=16)]
Kind = Literal[
    "brief_analysis", "creative_strategy", "content_plan", "copywriting", "report_summary"
]


class Structured(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Audience(Structured):
    description: Text
    primary_needs: Notes


class Analysis(Structured):
    objective_summary: Text
    target_audience: Audience
    key_themes: Notes
    content_pillars: Nonempty
    missing_information: Notes
    potential_risks: Notes
    creative_constraints: Notes


class Direction(Structured):
    concept_name: Title
    strategic_rationale: Text
    key_message: Text
    audience_insight: Text
    tone_of_voice: Text
    visual_direction: Text
    suggested_channels: Annotated[list[Channel], Field(min_length=1, max_length=8)]
    risks: Notes


class Strategy(Structured):
    creative_directions: Annotated[list[Direction], Field(min_length=1, max_length=5)]


class PlanItem(Structured):
    title: Title
    content_pillar: Text
    channel: Channel
    content_format: Title
    objective: Text
    key_message: Text
    draft_caption: Text
    visual_direction: Text
    call_to_action: Text
    suggested_day_offset: Annotated[int, Field(ge=0, le=365)]


class Plan(Structured):
    content_plan: Annotated[list[PlanItem], Field(min_length=1, max_length=10)]


class Copy(Structured):
    headline: Title
    caption: Text
    call_to_action: Text
    hashtags: Notes
    revision_notes: Notes
    potential_risks: Notes


class Summary(Structured):
    executive_summary: Text
    completed_work: Notes
    pending_activities: Notes
    risks: Notes
    recommended_next_actions: Notes


SCHEMAS: dict[str, type[Structured]] = {
    "brief_analysis": Analysis,
    "creative_strategy": Strategy,
    "content_plan": Plan,
    "copywriting": Copy,
    "report_summary": Summary,
}
PROMPT_VERSION = "creative-v2"
REPORT_PROMPT_VERSION = "creative-v1"
PROMPTS_V1 = {
    "brief_analysis": "Summarize the supplied objective and explicit requirements. Identify missing information. Label suggested pillars and distinguish them from client facts.",
    "creative_strategy": "Use the approved brief and validated analysis to propose distinct creative directions. Describe audience insights as hypotheses unless supplied research supports them.",
    "content_plan": "Use only the selected approved direction and snapshot. Return exactly the requested number of proposals using the permitted channels. Suggested days are provisional.",
    "copywriting": "Suggest draft copy for the supplied deliverable and exact revision. Incorporate the supplied human feedback. Preserve restrictions and avoid unsupported claims.",
    "report_summary": "Summarize only the supplied verified metrics. Use numbers as provided. Never compute or invent measurements. Keep all recommendations separate from facts.",
}
PROMPTS_V2 = {
    "brief_analysis": (
        "Analyze the approved brief as the source of truth. Summarize confirmed facts without adding "
        "product attributes or audience needs. Label unsupported audience interpretations as "
        "hypotheses, not facts. Put actionable gaps such as an unconfirmed CTA destination or "
        "usable asset rights in missing_information; do not request prohibited claims as if "
        "they were needed. Make content_pillars editorial themes, not tone instructions or "
        "channels. Preserve every explicit restriction in creative_constraints. Distinguish "
        "proposals from supplied facts and omit unknown details."
    ),
    "creative_strategy": (
        "Use the approved brief and analysis, but treat the brief as authoritative if they differ. "
        "Propose genuinely distinct concepts with different narrative angles and audience "
        "motivations, not merely different channels or formats. Label audience insights as "
        "hypotheses unless research was supplied. Do not invent product facts, testimonials, "
        "available media, or a working signup destination. Carry the brief's restrictions into "
        "every concept and describe proposed visuals as proposals requiring available assets."
    ),
    "content_plan": (
        "Use the approved brief and selected direction. Return exactly target_count distinct items, "
        "using only requested channels and the requested formats. Give each item a different "
        "content purpose. Do not invent fruit varieties, attributes, availability, or other "
        "unsupported claims. If the signup destination is unconfirmed, use a destination-neutral "
        "waitlist CTA; do not say link in bio or imply a working form. Describe visuals as "
        "proposed uses of assets, not proof that assets or rights exist. Suggested day offsets "
        "are provisional, never confirmed dates."
    ),
    "copywriting": (
        "Return one structured copy suggestion for the selected item and exact current revision. "
        "Use the approved brief as the fact source and honor its restrictions even if the plan "
        "or revision contains unsupported wording. When feedback requests improvement, make a "
        "useful editorial revision; do not repeat both the entire caption and CTA verbatim "
        "unless the feedback expressly requests faithful preservation. Keep hashtags grounded "
        "and omit unsupported product attributes. Use a destination-neutral waitlist CTA when "
        "the signup destination is unconfirmed. Revision notes must describe actual changes; "
        "never claim compliance without checking the copy. If no safe improvement is possible, "
        "keep supported wording and explain the limitation in revision_notes and potential_risks "
        "within the existing single-suggestion schema."
    ),
    "report_summary": PROMPTS_V1["report_summary"],
}
PROMPTS_V3 = PROMPTS_V2 | {
    "creative_strategy": (
        "Use the approved brief as authoritative and preserve every restriction. Separate verified "
        "brief facts from creative proposals and explicitly labeled audience hypotheses. Without "
        "research, phrase every audience insight as a hypothesis. Do not invent product or sensory "
        "attributes, availability, operational promises, a functional waitlist form or URL, signup "
        "fields, notification priority, or 'be the first to hear.' Describe visuals only as proposed "
        "assets requiring availability and rights confirmation. Generate multiple conceptually "
        "distinct directions with different narrative angles, not format-only variations, while "
        "covering the requested Instagram carousel, Instagram caption, and Website section."
    )
}
PROMPT_REGISTRY = {
    "creative-v1": PROMPTS_V1,
    "creative-v2": PROMPTS_V2,
    "creative-v3": PROMPTS_V3,
}


def prompt_for(kind: str, version: str) -> str:
    try:
        return PROMPT_REGISTRY[version][kind]
    except KeyError as err:
        raise GenerationFailure("unsupported_prompt_version") from err
TEMPERATURES = {
    "brief_analysis": 0.2,
    "creative_strategy": 0.6,
    "content_plan": 0.4,
    "copywriting": 0.5,
    "report_summary": 0.2,
}


class GenerationFailure(Exception):
    def __init__(self, code: str, retryable: bool = False, detail: str | None = None):
        self.code = code
        self.retryable = retryable
        self.detail = detail
        super().__init__(code if detail is None else f"{code}:{detail}")


class DuplicateJsonKey(ValueError):
    def __init__(self, key: str):
        self.key = key
        super().__init__(f"duplicate JSON object key: {key}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKey(key)
        value[key] = item
    return value


def strict_json_loads(raw: str) -> Any:
    """Parse JSON while rejecting duplicate object keys at every nesting level."""
    try:
        return json.loads(raw, object_pairs_hook=_strict_object)
    except DuplicateJsonKey as err:
        raise GenerationFailure("duplicate_json_key", True, err.key) from err
    except json.JSONDecodeError as err:
        raise GenerationFailure("invalid_output", True, str(err)) from err


def validate(kind: str, raw: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = SCHEMAS[kind].model_validate(strict_json_loads(raw))
    except GenerationFailure:
        raise
    except ValidationError as err:
        raise GenerationFailure("invalid_output", True) from err
    if isinstance(parsed, Plan) and (
        len(parsed.content_plan) != params["target_count"]
        or any(i.channel not in params["channels"] for i in parsed.content_plan)
    ):
        raise GenerationFailure("invalid_plan", True)
    return parsed.model_dump(mode="json")
