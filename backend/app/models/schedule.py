from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def class_key():
    return ForeignKeyConstraint(
        ["class_id", "organization_id"], ["learning_classes.id", "learning_classes.organization_id"]
    )


def teacher_key():
    return ForeignKeyConstraint(
        ["teacher_profile_id", "organization_id"],
        ["teacher_profiles.id", "teacher_profiles.organization_id"],
    )


class ClassTeacher(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "class_teachers"
    __table_args__ = (
        class_key(),
        teacher_key(),
        UniqueConstraint("class_id", "teacher_profile_id"),
        UniqueConstraint("class_id", "teacher_profile_id", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    teacher_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    override_reason: Mapped[str] = mapped_column(String(500), default="")


class SchedulePlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schedule_plans"
    __table_args__ = (
        class_key(),
        UniqueConstraint("class_id"),
        CheckConstraint("ends_on >= starts_on", name="ck_plan_dates"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    starts_on: Mapped[date]
    ends_on: Mapped[date]
    slots: Mapped[list] = mapped_column(JSON)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_key: Mapped[UUID | None] = mapped_column(Uuid)
    preview_digest: Mapped[str | None] = mapped_column(String(64))


class ClassSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "class_sessions"
    __table_args__ = (
        class_key(),
        ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        ForeignKeyConstraint(
            ["room_id", "branch_id", "organization_id"],
            ["rooms.id", "rooms.branch_id", "rooms.organization_id"],
        ),
        UniqueConstraint("class_id", "starts_at"),
        UniqueConstraint("id", "class_id", "organization_id"),
        CheckConstraint("ends_at > starts_at", name="ck_session_times"),
        CheckConstraint("capacity >= 1", name="ck_session_capacity"),
        CheckConstraint("format IN ('offline', 'online', 'hybrid')", name="ck_session_format"),
        CheckConstraint(
            "(format = 'online' AND room_id IS NULL) OR "
            "(format <> 'online' AND room_id IS NOT NULL)",
            name="ck_session_room_format",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    branch_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    room_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int]
    format: Mapped[str] = mapped_column(String(16))


class SessionTeacher(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "session_teachers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        ForeignKeyConstraint(
            ["class_id", "teacher_profile_id", "organization_id"],
            [
                "class_teachers.class_id",
                "class_teachers.teacher_profile_id",
                "class_teachers.organization_id",
            ],
        ),
        teacher_key(),
        UniqueConstraint("session_id", "teacher_profile_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    teacher_profile_id: Mapped[UUID] = mapped_column(Uuid, index=True)
