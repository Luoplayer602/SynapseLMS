"""Published, closed-answer practice and tenant-local daily rewards."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PracticeQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "practice_questions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        ForeignKeyConstraint(
            ["course_id", "organization_id"], ["courses.id", "courses.organization_id"]
        ),
        CheckConstraint("status IN ('draft','published','hidden')"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid)
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    ai_run_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("ai_runs.id"))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    locale: Mapped[str] = mapped_column(String(2))
    stem: Mapped[str] = mapped_column(String(1000))
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(String(1000), default="")
    source_refs: Mapped[list] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PracticeAttempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint("organization_id", "student_id", "request_key"),
        UniqueConstraint("organization_id", "student_id", "question_id"),
        UniqueConstraint("id", "organization_id"),
        ForeignKeyConstraint(
            ["student_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
        ForeignKeyConstraint(
            ["question_id", "organization_id"],
            ["practice_questions.id", "practice_questions.organization_id"],
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    question_id: Mapped[UUID] = mapped_column(Uuid)
    request_key: Mapped[UUID] = mapped_column(Uuid)
    answer_index: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    local_day: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64))


class PracticeDay(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "practice_days"
    __table_args__ = (
        UniqueConstraint("organization_id", "student_id", "local_day"),
        ForeignKeyConstraint(
            ["student_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
        ForeignKeyConstraint(
            ["attempt_id", "organization_id"],
            ["practice_attempts.id", "practice_attempts.organization_id"],
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    student_id: Mapped[UUID] = mapped_column(Uuid)
    local_day: Mapped[date] = mapped_column(Date)
    timezone: Mapped[str] = mapped_column(String(64))
    attempt_id: Mapped[UUID] = mapped_column(Uuid)
    streak: Mapped[int] = mapped_column(Integer)


class ThemeGrant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "theme_grants"
    __table_args__ = (
        UniqueConstraint("organization_id", "student_id", "theme"),
        ForeignKeyConstraint(
            ["student_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
        ForeignKeyConstraint(["earned_day_id"], ["practice_days.id"]),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    student_id: Mapped[UUID] = mapped_column(Uuid)
    theme: Mapped[str] = mapped_column(String(32))
    earned_day_id: Mapped[UUID] = mapped_column(Uuid)


class ThemeSelection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "theme_selections"
    __table_args__ = (
        UniqueConstraint("organization_id", "student_id"),
        ForeignKeyConstraint(
            ["student_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    student_id: Mapped[UUID] = mapped_column(Uuid)
    theme: Mapped[str] = mapped_column(String(32), default="synapse-soft")
