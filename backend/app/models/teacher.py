from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TeacherProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_profiles"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        UniqueConstraint("id", "organization_id"),
        CheckConstraint("version >= 1", name="ck_teacher_version"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(40), default="")
    introduction: Mapped[str] = mapped_column(Text, default="")
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


def profile_key():
    return ForeignKeyConstraint(
        ["teacher_profile_id", "organization_id"],
        ["teacher_profiles.id", "teacher_profiles.organization_id"],
    )


class TeachingCapability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teaching_capabilities"
    __table_args__ = (
        profile_key(),
        ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        UniqueConstraint("teacher_profile_id", "language_id"),
        UniqueConstraint("id", "teacher_profile_id", "organization_id"),
        UniqueConstraint("id", "organization_id", "language_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    teacher_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


def level_key():
    return ForeignKeyConstraint(
        ["level_id", "framework_id", "organization_id", "language_id"],
        [
            "course_levels.id",
            "course_levels.framework_id",
            "course_levels.organization_id",
            "course_levels.language_id",
        ],
    )


class TeachingCapabilityLevel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "teaching_capability_levels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["capability_id", "organization_id", "language_id"],
            [
                "teaching_capabilities.id",
                "teaching_capabilities.organization_id",
                "teaching_capabilities.language_id",
            ],
        ),
        level_key(),
        UniqueConstraint("capability_id", "level_id"),
    )
    capability_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    level_id: Mapped[UUID] = mapped_column(Uuid)


class TeacherCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_credentials"
    __table_args__ = (
        profile_key(),
        UniqueConstraint("id", "teacher_profile_id", "organization_id"),
        CheckConstraint(
            "issued_on IS NULL OR expires_on IS NULL OR expires_on >= issued_on",
            name="ck_teacher_credential_dates",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    teacher_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(200))
    issuer: Mapped[str] = mapped_column(String(200), default="")
    issued_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class TeacherHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teacher_history"
    __table_args__ = (
        profile_key(),
        ForeignKeyConstraint(
            ["capability_id", "organization_id", "language_id"],
            [
                "teaching_capabilities.id",
                "teaching_capabilities.organization_id",
                "teaching_capabilities.language_id",
            ],
        ),
        ForeignKeyConstraint(
            ["capability_id", "teacher_profile_id", "organization_id"],
            [
                "teaching_capabilities.id",
                "teaching_capabilities.teacher_profile_id",
                "teaching_capabilities.organization_id",
            ],
        ),
        ForeignKeyConstraint(
            ["credential_id", "teacher_profile_id", "organization_id"],
            [
                "teacher_credentials.id",
                "teacher_credentials.teacher_profile_id",
                "teacher_credentials.organization_id",
            ],
        ),
        ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        CheckConstraint(
            "(capability_id IS NOT NULL AND credential_id IS NULL "
            "AND language_id IS NOT NULL) OR "
            "(credential_id IS NOT NULL AND capability_id IS NULL AND language_id IS NULL)",
            name="ck_teacher_history_target",
        ),
        UniqueConstraint("capability_id", "version"),
        UniqueConstraint("credential_id", "version"),
        UniqueConstraint("id", "organization_id", "language_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    teacher_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    capability_id: Mapped[UUID | None] = mapped_column(Uuid)
    credential_id: Mapped[UUID | None] = mapped_column(Uuid)
    language_id: Mapped[UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    version: Mapped[int]
    public_snapshot: Mapped[dict] = mapped_column(JSON)
    internal_snapshot: Mapped[dict] = mapped_column(JSON)


class TeacherHistoryLevel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "teacher_history_levels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["history_id", "organization_id", "language_id"],
            [
                "teacher_history.id",
                "teacher_history.organization_id",
                "teacher_history.language_id",
            ],
        ),
        level_key(),
        UniqueConstraint("history_id", "level_id"),
    )
    history_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    level_id: Mapped[UUID] = mapped_column(Uuid)
