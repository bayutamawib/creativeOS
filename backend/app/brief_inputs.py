from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, HttpUrl, StringConstraints

from app.schemas import Input

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Paragraph = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Channel = Literal["Instagram", "TikTok", "Facebook", "LinkedIn", "YouTube", "Website", "Email", "X"]
Category = Literal["brief_attachment", "brand_guideline", "creative_asset", "reference", "other"]
Visibility = Literal["internal", "client_visible"]


class Reference(Input):
    type: Literal["url"]
    value: HttpUrl


class BriefFields(Input):
    title: Short
    objective: Paragraph
    target_audience: Paragraph | None = None
    key_message: Paragraph | None = None
    tone_of_voice: Short | None = None
    content_type: Short | None = None
    preferred_channels: list[Channel] = Field(default_factory=list, max_length=8)
    requested_item_count: int = Field(default=3, ge=1, le=10)
    target_timeline: Short | None = None
    references: list[Reference] = Field(default_factory=list, max_length=10)
    restrictions: Paragraph | None = None
    additional_context: Paragraph | None = None
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=12)


class Version(Input):
    expected_version: int = Field(ge=1)
    feedback: Paragraph | None = None


class BriefEdit(Input):
    expected_version: int = Field(ge=1)
    title: Short | None = None
    objective: Paragraph | None = None
    target_audience: Paragraph | None = None
    key_message: Paragraph | None = None
    tone_of_voice: Short | None = None
    content_type: Short | None = None
    preferred_channels: list[Channel] | None = Field(None, max_length=8)
    requested_item_count: int | None = Field(None, ge=1, le=10)
    target_timeline: Short | None = None
    references: list[Reference] | None = Field(None, max_length=10)
    restrictions: Paragraph | None = None
    additional_context: Paragraph | None = None
    attachment_ids: list[UUID] | None = Field(None, max_length=12)
