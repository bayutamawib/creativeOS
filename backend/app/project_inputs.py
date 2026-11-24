from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.intake_inputs import Name
from app.schemas import Input

Priority = Literal["low", "medium", "high", "urgent"]
ProjectStatus = Literal[
    "draft", "planning", "in_progress", "in_review", "completed", "on_hold", "cancelled"
]
TaskStatus = Literal["todo", "in_progress", "in_review", "completed", "blocked", "cancelled"]
StageStatus = Literal["pending", "in_progress", "completed", "blocked"]
Portal = Literal["agency", "client"]
Description = Annotated[str, Field(max_length=5000)]


class ProjectUpdate(Input):
    name: Name | None = None
    description: Description | None = None
    service_type: Annotated[str, Field(max_length=100)] | None = None
    priority: Priority | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    due_date: date | None = None
    budget: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] | None = None


class ProjectCreate(ProjectUpdate):
    client_id: UUID
    name: Name


class MemberInput(Input):
    user_id: UUID
    project_role: Annotated[str, Field(max_length=50)] | None = None


class MilestoneUpdate(Input):
    name: Name | None = None
    description: Description | None = None
    due_date: date | None = None
    status: StageStatus | None = None
    client_visible: bool | None = None


class MilestoneCreate(MilestoneUpdate):
    name: Name


class TaskUpdate(Input):
    title: Name | None = None
    description: Description | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    milestone_id: UUID | None = None
    start_date: date | None = None
    due_date: date | None = None
    expected_updated_at: datetime | None = None


class TaskCreate(TaskUpdate):
    title: Name


class TaskAssignment(Input):
    user_id: UUID


class TaskTemplateApply(Input):
    template: Literal["social_media_campaign"]
    planning_start: date
    confirmed: Literal[True]
