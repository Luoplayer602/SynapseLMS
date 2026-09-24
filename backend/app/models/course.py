from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CourseLanguage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_languages"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("id", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class LevelFramework(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "level_frameworks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        UniqueConstraint("organization_id", "language_id", "code"),
        UniqueConstraint("id", "organization_id", "language_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class CourseLevel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_levels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        UniqueConstraint("organization_id", "framework_id", "code"),
        UniqueConstraint("organization_id", "framework_id", "rank"),
        UniqueConstraint("id", "framework_id", "organization_id", "language_id"),
        CheckConstraint("rank >= 1", name="ck_course_level_rank"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    rank: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        ForeignKeyConstraint(
            ["entry_level_id", "framework_id", "organization_id", "language_id"],
            [
                "course_levels.id",
                "course_levels.framework_id",
                "course_levels.organization_id",
                "course_levels.language_id",
            ],
        ),
        ForeignKeyConstraint(
            ["exit_level_id", "framework_id", "organization_id", "language_id"],
            [
                "course_levels.id",
                "course_levels.framework_id",
                "course_levels.organization_id",
                "course_levels.language_id",
            ],
        ),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_course_status"),
        CheckConstraint(
            "framework_id IS NULL OR language_id IS NOT NULL", name="ck_course_framework_language"
        ),
        CheckConstraint(
            "(entry_level_id IS NULL AND exit_level_id IS NULL) OR framework_id IS NOT NULL",
            name="ck_course_level_framework",
        ),
        CheckConstraint(
            "status <> 'published' OR (language_id IS NOT NULL AND exit_level_id IS NOT NULL "
            "AND length(trim(objectives)) > 0)",
            name="ck_course_published",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    language_id: Mapped[UUID | None] = mapped_column(Uuid)
    framework_id: Mapped[UUID | None] = mapped_column(Uuid)
    entry_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    exit_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    objectives: Mapped[str] = mapped_column(Text, default="")
    entry_requirements: Mapped[str] = mapped_column(Text, default="")
    completion_requirements: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}
