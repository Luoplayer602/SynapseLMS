from datetime import date, time
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.api.schemas import Input


class TeacherAssignment(Input):
    version: int = Field(ge=1)
    teacher_ids: list[UUID] = Field(max_length=20)
    override_reason: str = Field(default="", max_length=500)

    @field_validator("teacher_ids")
    @classmethod
    def unique_teachers(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("Duplicate teachers")
        return values


class WeeklySlot(Input):
    weekday: int = Field(ge=0, le=6)
    starts_at: time
    ends_at: time
    room_id: UUID | None = None
    teacher_ids: list[UUID] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def valid(self):
        if any(t.tzinfo or t.second or t.microsecond for t in (self.starts_at, self.ends_at)):
            raise ValueError("Use local hours and minutes only")
        if self.ends_at <= self.starts_at:
            raise ValueError("Same-day positive time interval required")
        if len(self.teacher_ids) != len(set(self.teacher_ids)):
            raise ValueError("Duplicate teachers")
        return self


class ScheduleDraft(Input):
    version: int = Field(ge=1)
    starts_on: date
    ends_on: date
    slots: list[WeeklySlot] = Field(min_length=1, max_length=14)

    @model_validator(mode="after")
    def valid(self):
        if not 0 <= (self.ends_on - self.starts_on).days <= 365:
            raise ValueError("Range must be at most 366 days")
        return self


class ScheduleConfirmation(Input):
    version: int = Field(ge=1)
    preview_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation_key: UUID
