from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

Password = Annotated[str, Field(min_length=12, max_length=128)]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Reason = Annotated[str, Field(min_length=3, max_length=500)]
Role = Literal["organization_manager", "staff", "teacher", "student"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def trim_text(cls, value, info):
        if isinstance(value, str) and info.field_name not in {"password", "current_password"}:
            return value.strip()
        return value


class Login(Input):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class Register(Input):
    email: EmailStr
    password: Password
    display_name: Name
    organization_id: UUID | None = None
    invite_code: Annotated[str, Field(min_length=20, max_length=128)] | None = None

    @model_validator(mode="after")
    def select_registration_method(self):
        if (self.organization_id is None) == (self.invite_code is None):
            raise ValueError("Select exactly one organization or invite code")
        return self


class OrganizationCreate(Input):
    name: Name
    slug: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{1,79}$")]
    is_public: bool = False
    registration_enabled: bool = False


class OrganizationChange(Input):
    is_active: bool
    is_public: bool
    registration_enabled: bool
    reason: Reason


class InviteCreate(Input):
    max_uses: int = Field(default=1, ge=1, le=1000)
    expires_days: int = Field(default=7, ge=1, le=30)


class MemberCreate(Input):
    email: EmailStr
    password: Password
    display_name: Name
    role: Role
    reason: Reason


class MemberChange(Input):
    role: Role
    is_active: bool
    reason: Reason


class SupportCreate(Input):
    organization_id: UUID
    reason: Reason
    minutes: int = Field(default=30, ge=1, le=60)


class UserChange(Input):
    is_active: bool
    reason: Reason


class PasswordChange(Input):
    current_password: Annotated[str, Field(min_length=1, max_length=128)]
    password: Password


class EmailRequest(Input):
    email: EmailStr


class TokenInput(Input):
    token: Annotated[str, Field(min_length=32, max_length=128)]


class PasswordReset(TokenInput):
    password: Password


class RevokeSessions(Input):
    scope: Literal["others", "all"]


class MembershipInviteCreate(Input):
    email: EmailStr
    display_name: Name
    role: Role
    reason: Reason
    expires_days: int = Field(default=7, ge=1, le=30)


class MembershipInviteResend(Input):
    reason: Reason
    expires_days: int = Field(default=7, ge=1, le=30)


class InvitationReason(Input):
    reason: Reason


class AcceptNewInvitation(TokenInput):
    display_name: Name
    password: Password
