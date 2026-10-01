from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Task = Literal["class_recommendation", "practice_generation", "progress_summary"]
Kind = Literal["openai", "gemini", "claude", "openai_compatible", "ollama", "lm_studio"]


class ProviderInput(BaseModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    kind: Kind
    base_url: str = Field(default="", max_length=2048)
    model_id: str = Field(min_length=1, max_length=160)
    api_key: str | None = Field(default=None, max_length=2048)
    enabled: bool = False
    allowed_tasks: list[Task] = Field(default_factory=list)
    timeout_seconds: int = Field(default=20, ge=3, le=60)
    max_output_tokens: int = Field(default=1024, ge=128, le=4096)
    max_daily_calls: int = Field(default=100, ge=1, le=10000)
    version: int | None = Field(default=None, ge=1)


class RouteInput(BaseModel):
    task: Task
    provider_ids: list[UUID] = Field(max_length=5)


class TenantTaskInput(BaseModel):
    task: Task
    enabled: bool
    max_daily_calls: int = Field(default=30, ge=1, le=1000)
    timezone: str = Field(default="Asia/Ho_Chi_Minh", max_length=64)


class PromptInput(BaseModel):
    task: Task
    locale: Literal["vi", "en"]
    body: str


class PromptPublish(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
