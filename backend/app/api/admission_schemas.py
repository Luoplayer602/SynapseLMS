from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: UUID


class Change(Input):
    version: int = Field(ge=0)


class Installment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: int = Field(ge=0, le=730)
    percent: int = Field(ge=1, le=100)


class FeeInput(Change):
    amount: int = Field(ge=0, le=1_000_000_000, strict=True)
    installments: list[Installment] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def valid(self):
        days = [i.days for i in self.installments]
        if sum(i.percent for i in self.installments) != 100 or days != sorted(set(days)):
            raise ValueError("Installments must total 100%, with unique ascending days")
        return self


class SettingsInput(Change):
    block_debt: bool


class OpeningInput(Change):
    enabled: bool


class DiscountInput(Input):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    course_id: UUID | None = None
    kind: Literal["fixed", "percent"]
    value: int = Field(ge=1, le=1_000_000_000, strict=True)
    starts_on: date
    ends_on: date
    max_uses: int = Field(ge=1, le=1_000_000)

    @model_validator(mode="after")
    def valid(self):
        if self.ends_on < self.starts_on or (self.kind == "percent" and self.value > 100):
            raise ValueError("Invalid discount")
        return self


class DiscountState(Change):
    active: bool


class Availability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weekday: int = Field(ge=0, le=6)
    starts_at: time
    ends_at: time

    @model_validator(mode="after")
    def valid(self):
        if self.starts_at >= self.ends_at or self.starts_at.tzinfo or self.ends_at.tzinfo:
            raise ValueError("Availability must be same-day local time")
        return self


class RequestInput(Input):
    student_id: UUID | None = None
    course_id: UUID
    branch_id: UUID | None = None
    format: Literal["any", "offline", "online", "hybrid"] = "any"
    availability: list[Availability] = Field(default_factory=list, max_length=28)
    discount_code: str = Field(default="", max_length=40)


class DecisionInput(Change):
    action: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=500)


class PlacementInput(Change):
    class_id: UUID
    reason: str = Field(min_length=3, max_length=500)


class PaymentInput(Input):
    amount: int = Field(ge=1, le=1_000_000_000, strict=True)
    method: Literal["cash", "transfer"]
    reference: str = Field(default="", max_length=200)


class ReverseInput(Input):
    reason: str = Field(min_length=3, max_length=500)


class AttendanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    student_id: UUID
    status: Literal["unmarked", "present", "absent", "late", "excused"]
    note: str = Field(default="", max_length=500)


class AttendanceInput(Change):
    records: list[AttendanceRecord] = Field(max_length=10000)
    finalized: bool
    reason: str = Field(default="", max_length=500)
