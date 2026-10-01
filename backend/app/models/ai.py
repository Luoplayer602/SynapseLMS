"""AI configuration and immutable prompt/run records.

Provider credentials are ciphertext only. No tenant-owned run may cross an org FK.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AIProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_providers"
    __table_args__ = (
        UniqueConstraint("code"),
        CheckConstraint(
            "kind IN ('openai','gemini','claude','openai_compatible','ollama','lm_studio')"
        ),
    )

    code: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(2048), default="")
    model_id: Mapped[str] = mapped_column(String(160))
    credential_ciphertext: Mapped[str | None] = mapped_column(Text)
    credential_key_version: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20)
    max_output_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    max_daily_calls: Mapped[int] = mapped_column(Integer, default=100)
    allowed_tasks: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}


class AIRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_routes"
    __table_args__ = (
        UniqueConstraint("task", "priority"),
        UniqueConstraint("task", "provider_id"),
    )

    task: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ai_providers.id"))
    priority: Mapped[int] = mapped_column(Integer)


class AITenantSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_tenant_settings"
    __table_args__ = (UniqueConstraint("organization_id", "task"),)

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    task: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    max_daily_calls: Mapped[int] = mapped_column(Integer, default=30)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Ho_Chi_Minh")


class AIPrompt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_prompts"
    __table_args__ = (
        UniqueConstraint("task", "locale", "revision"),
        CheckConstraint("status IN ('draft','tested','published','retired')"),
    )

    task: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(2))
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    body: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))


class AIActivePrompt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_active_prompts"
    __table_args__ = (UniqueConstraint("task", "locale"),)

    task: Mapped[str] = mapped_column(String(32))
    locale: Mapped[str] = mapped_column(String(2))
    prompt_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ai_prompts.id"))


class AIRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        ForeignKeyConstraint(["provider_id"], ["ai_providers.id"]),
        ForeignKeyConstraint(["prompt_id"], ["ai_prompts.id"]),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    task: Mapped[str] = mapped_column(String(32))
    provider_id: Mapped[UUID | None] = mapped_column(Uuid)
    prompt_id: Mapped[UUID | None] = mapped_column(Uuid)
    input_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24))
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    source_refs: Mapped[list] = mapped_column(JSON, default=list)


class AIProgressCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_progress_cache"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "viewer_id",
            "scope",
            "locale",
            "source_digest",
            "prompt_id",
            "route_digest",
        ),
        ForeignKeyConstraint(
            ["ai_run_id", "organization_id"], ["ai_runs.id", "ai_runs.organization_id"]
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    viewer_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    scope: Mapped[str] = mapped_column(String(80))
    locale: Mapped[str] = mapped_column(String(2))
    source_digest: Mapped[str] = mapped_column(String(64))
    prompt_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("ai_prompts.id"))
    route_digest: Mapped[str] = mapped_column(String(64))
    highlight_ids: Mapped[list] = mapped_column(JSON)
    next_step: Mapped[str] = mapped_column(String(32))
    ai_run_id: Mapped[UUID] = mapped_column(Uuid)
