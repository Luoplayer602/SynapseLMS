from datetime import date
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.api.course_schemas import NamedCode
from app.api.schemas import Input, Name, Reason


class BranchFields(Input):
    name: Name
    address: str = Field(default="", max_length=5000)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError("Unknown IANA timezone") from error
        return value


class BranchCreate(BranchFields, NamedCode):
    pass


class BranchChange(BranchFields):
    version: int = Field(ge=1)


class RoomFields(Input):
    name: Name
    capacity: int = Field(ge=1, le=10000)
    notes: str = Field(default="", max_length=5000)


class RoomCreate(RoomFields, NamedCode):
    branch_id: UUID


class RoomChange(RoomFields):
    version: int = Field(ge=1)


class FacilityState(Input):
    version: int = Field(ge=1)
    archived: bool
    reason: Reason


class ClassFields(Input):
    name: Name
    branch_id: UUID
    room_id: UUID | None = None
    capacity: int = Field(ge=1, le=10000)
    starts_on: date
    ends_on: date
    format: Literal["offline", "online", "hybrid"]

    @model_validator(mode="after")
    def validate_relationships(self):
        if self.ends_on < self.starts_on:
            raise ValueError("End precedes start")
        if self.format == "online" and self.room_id:
            raise ValueError("Online classes cannot use a room")
        return self


class ClassCreate(ClassFields, NamedCode):
    course_id: UUID


class ClassChange(ClassFields):
    version: int = Field(ge=1)


class ClassState(Input):
    version: int = Field(ge=1)
    status: Literal["draft", "archived"]
    reason: Reason
