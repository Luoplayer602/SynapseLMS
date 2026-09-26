from datetime import date
from uuid import UUID

from pydantic import Field, model_validator

from app.api.schemas import Input, Name, Reason


class PersonalTeacher(Input):
    phone: str = Field(default="", max_length=40)
    introduction: str = Field(default="", max_length=5000)


class TeacherFields(PersonalTeacher):
    full_name: Name
    internal_notes: str = Field(default="", max_length=5000)


class TeacherCreate(TeacherFields):
    user_id: UUID


class TeacherChange(TeacherFields):
    version: int = Field(ge=1)


class PersonalTeacherChange(PersonalTeacher):
    version: int = Field(ge=1)


class TeacherArchive(Input):
    version: int = Field(ge=1)
    archived: bool
    reason: Reason


class CapabilityFields(Input):
    level_ids: list[UUID] = Field(default_factory=list, max_length=100)
    reason: Reason

    @model_validator(mode="after")
    def unique_levels(self):
        if len(set(self.level_ids)) != len(self.level_ids):
            raise ValueError("Duplicate levels")
        return self


class CapabilityCreate(CapabilityFields):
    language_id: UUID


class CapabilityChange(CapabilityFields):
    version: int = Field(ge=1)


class CredentialFields(Input):
    name: Name
    issuer: str = Field(default="", max_length=200)
    issued_on: date | None = None
    expires_on: date | None = None
    internal_notes: str = Field(default="", max_length=5000)
    reason: Reason

    @model_validator(mode="after")
    def date_order(self):
        if self.issued_on and self.expires_on and self.expires_on < self.issued_on:
            raise ValueError("Expiry precedes issue date")
        return self


class CredentialChange(CredentialFields):
    version: int = Field(ge=1)


class TeacherRecordState(Input):
    version: int = Field(ge=1)
    revoked: bool
    reason: Reason
