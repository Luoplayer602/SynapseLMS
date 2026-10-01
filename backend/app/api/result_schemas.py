from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_key: UUID


class Component(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    name: str = Field(min_length=1, max_length=200)
    skill: Literal["listening", "speaking", "reading", "writing", "general"]
    max_score: Decimal = Field(gt=0, le=10000, max_digits=7, decimal_places=2)
    weight: int = Field(ge=1, le=10000, strict=True)


class SchemeCreate(Input):
    course_id: UUID
    name: str = Field(min_length=1, max_length=200)
    components: list[Component] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_components(self):
        codes = [c.code.lower() for c in self.components]
        if len(codes) != len(set(codes)):
            raise ValueError("Component codes must be unique")
        return self


class SchemeChange(SchemeCreate):
    version: int = Field(ge=1)


class VersionInput(Input):
    version: int = Field(ge=0)


class ItemTiming(VersionInput):
    assessed_at: datetime
    session_id: UUID | None = None

    @field_validator("assessed_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value


class ScoreInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enrollment_id: UUID
    score: Decimal | None = Field(default=None, ge=0, le=10000, max_digits=7, decimal_places=2)
    comment: str = Field(default="", max_length=1000)


class ScoreSave(VersionInput):
    scores: list[ScoreInput] = Field(max_length=10000)
    reason: str = Field(default="", max_length=500)


class Publication(VersionInput):
    publish_at: datetime

    @field_validator("publish_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timezone required")
        return value


class LockChange(VersionInput):
    reason: str = Field(min_length=3, max_length=500)
