from datetime import date
from typing import Annotated
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.api.schemas import Input, Name, Reason
from app.core.security import now

Phone = Annotated[str, Field(min_length=5, max_length=30, pattern=r"^\+?[0-9() .-]+$")]


class GuardianInput(Input):
    full_name: Name
    relationship: Annotated[str, Field(min_length=1, max_length=100)]
    phone: Phone
    email: EmailStr | None = None
    is_primary: bool = False

    @field_validator("phone")
    @classmethod
    def digits_required(cls, value):
        if sum(c.isdigit() for c in value) < 5:
            raise ValueError("Phone requires at least five digits")
        return value


class PersonalProfile(Input):
    full_name: Name
    date_of_birth: date | None = None
    phone: Phone | None = None
    address: Annotated[str, Field(max_length=500)] | None = None
    guardians: list[GuardianInput] = Field(default_factory=list, max_length=10)

    @field_validator("date_of_birth")
    @classmethod
    def past_birth(cls, value):
        if value and value > now().date():
            raise ValueError("Birth date cannot be in the future")
        return value

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value):
        return GuardianInput.digits_required(value) if value else value

    @model_validator(mode="after")
    def one_primary(self):
        if sum(item.is_primary for item in self.guardians) > 1:
            raise ValueError("Only one primary guardian is allowed")
        return self


class PersonalChange(PersonalProfile):
    version: int = Field(ge=1)


class StudentCreate(PersonalProfile):
    user_id: UUID
    internal_notes: Annotated[str, Field(max_length=5000)] = ""


class StudentChange(PersonalChange):
    internal_notes: Annotated[str, Field(max_length=5000)] = ""


class ArchiveStudent(Input):
    version: int = Field(ge=1)
    archived: bool
    reason: Reason
