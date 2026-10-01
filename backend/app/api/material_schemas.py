from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator


class MaterialCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    source: str = Field(default="", max_length=500)
    language: str = Field(default="", max_length=32)
    audience: str = Field(default="students", pattern="^(students|teachers)$")
    class_id: UUID | None = None
    session_id: UUID | None = None


class LinkVersion(BaseModel):
    url: HttpUrl
    request_key: UUID

    @model_validator(mode="after")
    def https_only(self):
        if self.url.scheme != "https":
            raise ValueError("HTTPS required")
        return self


class Decision(BaseModel):
    reason: str = Field(default="", max_length=500)


class AssignmentCreate(BaseModel):
    material_version_id: UUID
    class_id: UUID
    session_id: UUID | None = None
    publish_at: datetime | None = None
    request_key: UUID


class CurriculumCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    author: str = Field(default="", max_length=200)
    publisher: str = Field(default="", max_length=200)
    edition: str = Field(default="", max_length=100)
    isbn: str = Field(default="", max_length=32)
    language: str = Field(default="", max_length=32)


class UnitInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=1)
    parent_id: UUID | None = None


class UnitMaterialInput(BaseModel):
    material_version_id: UUID
    page_hint: str = Field(default="", max_length=100)
    required: bool = False


class CurriculumBind(BaseModel):
    curriculum_version_id: UUID
    primary: bool = False
    reason: str = Field(default="", max_length=500)


class QuotaInput(BaseModel):
    quota_bytes: int = Field(ge=1, le=2_147_483_648)


class VersionChange(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    source: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=32)
    audience: str | None = Field(default=None, pattern="^(students|teachers)$")
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def at_least_one(self):
        if not any(
            getattr(self, field) is not None
            for field in ("title", "description", "source", "language", "audience")
        ):
            raise ValueError("At least one field is required")
        return self
