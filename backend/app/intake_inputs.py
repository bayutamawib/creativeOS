from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.schemas import Input

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Inquiry(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    company_name: Name
    contact_name: str = Field(min_length=1, max_length=150)
    email: EmailStr
    phone: str | None = Field(None, max_length=30)
    industry: str | None = Field(None, max_length=100)
    service_interest: str | None = Field(None, max_length=500)
    inquiry_message: str | None = Field(None, max_length=5000)
    website_confirmation: str = Field("", max_length=0)


class LeadUpdate(Input):
    status: Literal["new", "contacted", "qualified", "proposal_sent"] | None = None
    notes: str | None = Field(None, max_length=5000)


class Assign(Input):
    user_id: UUID | None


class Convert(Input):
    brand_name: Name | None = None
    industry: str | None = Field(None, max_length=100)
    create_initial_project: bool = False
    initial_project_name: Name | None = None

    @model_validator(mode="after")
    def check_project(self) -> Self:
        if self.create_initial_project != bool(self.initial_project_name):
            raise ValueError("Provide a project name when creating an initial project")
        return self


class ClientInvite(Input):
    email: EmailStr
    role: Literal["client_admin", "client_member"]


class FormSubmission(Input):
    source_submission_id: Name
    inquiry: Inquiry
