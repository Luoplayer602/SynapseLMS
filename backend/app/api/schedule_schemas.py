from datetime import date, time
from typing import Literal
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


class SessionOperation(Input):
    version: int = Field(ge=1)
    action: Literal["reschedule", "substitute", "cancel", "restore"]
    reason: str = Field(min_length=3, max_length=500)
    request_key: UUID
    day: date | None = None
    starts_at: time | None = None
    ends_at: time | None = None
    room_id: UUID | None = None
    teacher_ids: list[UUID] | None = Field(default=None, min_length=1, max_length=20)
    override_reason: str = Field(default="", max_length=500)

    @model_validator(mode="after")
    def valid_operation(self):
        if self.action == "reschedule":
            if self.day is None or self.starts_at is None or self.ends_at is None:
                raise ValueError("Date and times required")
            WeeklySlot(weekday=0, starts_at=self.starts_at, ends_at=self.ends_at)
        elif any(x is not None for x in (self.day, self.starts_at, self.ends_at, self.room_id)):
            raise ValueError("Only reschedule accepts time/room changes")
        if self.action == "substitute":
            if not self.teacher_ids or len(set(self.teacher_ids)) != len(self.teacher_ids):
                raise ValueError("Unique teachers required")
        elif self.teacher_ids is not None or self.override_reason:
            raise ValueError("Only substitution accepts teacher changes")
        return self
