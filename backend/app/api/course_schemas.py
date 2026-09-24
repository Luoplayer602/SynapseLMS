from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.api.schemas import Input, Name, Reason

Code = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{1,39}$")]


class NamedCode(Input):
    code: Code
    name: Name

    @field_validator("code", mode="before")
    @classmethod
    def uppercase(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class CatalogAction(Input):
    version: int = Field(ge=1)
    reason: Reason


class CatalogCodeAction(CatalogAction):
    code: Code

    @field_validator("code", mode="before")
    @classmethod
    def uppercase(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class FrameworkCreate(NamedCode):
    language_id: UUID


class LevelCreate(NamedCode):
    framework_id: UUID
    rank: int = Field(ge=1, le=10000)


class Rename(Input):
    name: Name
    version: int = Field(ge=1)


class CourseContent(Input):
    name: Name
    description: Annotated[str, Field(max_length=5000)] = ""
    objectives: Annotated[str, Field(max_length=5000)] = ""
    entry_requirements: Annotated[str, Field(max_length=5000)] = ""
    completion_requirements: Annotated[str, Field(max_length=5000)] = ""
    language_id: UUID | None = None
    framework_id: UUID | None = None
    entry_level_id: UUID | None = None
    exit_level_id: UUID | None = None


class CourseCreate(CourseContent, NamedCode):
    pass


class CourseChange(CourseContent):
    version: int = Field(ge=1)


class CourseState(Input):
    version: int = Field(ge=1)
    status: Literal["draft", "published", "archived"]
    reason: Reason
