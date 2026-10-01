from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class QuestionInput(BaseModel):
    course_id: UUID
    locale: Literal["vi", "en"] = "vi"
    stem: str = Field(min_length=10, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str = Field(default="", max_length=1000)


class GenerateInput(BaseModel):
    course_id: UUID
    locale: Literal["vi", "en"] = "vi"


class SubmitInput(BaseModel):
    request_key: UUID
    answer_index: int = Field(ge=0, le=3)


class ThemeInput(BaseModel):
    theme: Literal["synapse-soft", "neo-pop", "clay-garden", "liquid-glass"]
