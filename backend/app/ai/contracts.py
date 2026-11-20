"""Versioned creative service contracts shared by both providers."""

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
PROMPT_VERSION = "creative-v1"
PROMPTS = {
    "brief_analysis": "Summarize the supplied objective and explicit requirements. Identify missing information. Label suggested pillars and distinguish them from client facts.",
    "creative_strategy": "Use the approved brief and validated analysis to propose distinct creative directions. Describe audience insights as hypotheses unless supplied research supports them.",
    "content_plan": "Use only the selected approved direction and snapshot. Return exactly the requested number of proposals using the permitted channels. Suggested days are provisional.",
    "copywriting": "Suggest draft copy for the supplied deliverable and exact revision. Incorporate the supplied human feedback. Preserve restrictions and avoid unsupported claims.",
    "report_summary": "Summarize only the supplied verified metrics. Use numbers as provided. Never compute or invent measurements. Keep all recommendations separate from facts.",
}
TEMPERATURES = {
    "brief_analysis": 0.2,
    "creative_strategy": 0.6,
    "content_plan": 0.4,
    "copywriting": 0.5,
    "report_summary": 0.2,
}


class GenerationFailure(Exception):
    def __init__(self, code: str, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


def validate(kind: str, raw: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = SCHEMAS[kind].model_validate_json(raw)
    except ValidationError as err:
        raise GenerationFailure("invalid_output", True) from err
    if isinstance(parsed, Plan) and (
        len(parsed.content_plan) != params["target_count"]
        or any(i.channel not in params["channels"] for i in parsed.content_plan)
    ):
        raise GenerationFailure("invalid_plan", True)
    return parsed.model_dump(mode="json")
