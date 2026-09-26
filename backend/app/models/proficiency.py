from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def level_keys():
    return tuple(
        ForeignKeyConstraint(
            [field, "framework_id", "organization_id", "language_id"],
            [
                "course_levels.id",
                "course_levels.framework_id",
                "course_levels.organization_id",
                "course_levels.language_id",
            ],
        )
        for field in ("self_level_id", "verified_level_id", "goal_level_id")
    )


class StudentProficiency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_proficiencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["student_profile_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
        ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        UniqueConstraint("student_profile_id", "framework_id"),
        UniqueConstraint("id", "organization_id", "framework_id", "language_id"),
        CheckConstraint("version >= 1", name="ck_proficiency_version"),
        CheckConstraint(
            "(verified_level_id IS NULL AND verified_at IS NULL AND verified_by IS NULL) OR "
            "(verified_level_id IS NOT NULL AND verified_at IS NOT NULL "
            "AND verified_by IS NOT NULL)",
            name="ck_proficiency_verification",
        ),
        *level_keys(),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    student_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    self_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    self_declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    verification_source: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[str] = mapped_column(Text, default="")
    goal_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    goal_text: Mapped[str] = mapped_column(Text, default="")
    target_date: Mapped[date | None] = mapped_column(Date)
    goals_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class ProficiencyHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proficiency_history"
    __table_args__ = (
        ForeignKeyConstraint(
            ["proficiency_id", "organization_id", "framework_id", "language_id"],
            [
                "student_proficiencies.id",
                "student_proficiencies.organization_id",
                "student_proficiencies.framework_id",
                "student_proficiencies.language_id",
            ],
        ),
        UniqueConstraint("proficiency_id", "version"),
        *level_keys(),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    proficiency_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    self_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    verified_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    goal_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    version: Mapped[int]
    public_snapshot: Mapped[dict] = mapped_column(JSON)
    internal_snapshot: Mapped[dict] = mapped_column(JSON)
