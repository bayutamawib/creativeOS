from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgencyRole(StrEnum):
    ADMIN = "admin"
    MANAGER = "agency_manager"
    TEAM = "team_member"


class Login(Input):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=256)


class Invite(Input):
    email: EmailStr
    role: AgencyRole


class Redeem(Input):
    token: SecretStr = Field(min_length=32, max_length=200)
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    password: SecretStr | None = Field(default=None, min_length=12, max_length=256)


class Activation(Input):
    is_active: bool = Field(strict=True)


class Operational(Input):
    timezone: str = Field(max_length=80)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class Forgot(Input):
    email: EmailStr


class Reset(Input):
    token: SecretStr = Field(min_length=32, max_length=200)
    password: SecretStr = Field(min_length=12, max_length=256)
