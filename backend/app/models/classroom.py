from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Branch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        UniqueConstraint("id", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Ho_Chi_Minh")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class Room(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rooms"
    __table_args__ = (
        ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        UniqueConstraint("branch_id", "code"),
        UniqueConstraint("id", "branch_id", "organization_id"),
        CheckConstraint("capacity >= 1", name="ck_room_capacity"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    branch_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int]
    notes: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}


class LearningClass(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "learning_classes"
    __table_args__ = (
        Index("uq_learning_class_id_org", "id", "organization_id", unique=True),
        UniqueConstraint("organization_id", "code"),
        ForeignKeyConstraint(
            ["course_id", "organization_id"], ["courses.id", "courses.organization_id"]
        ),
        ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        ForeignKeyConstraint(
            ["room_id", "branch_id", "organization_id"],
            ["rooms.id", "rooms.branch_id", "rooms.organization_id"],
        ),
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
        *[
            ForeignKeyConstraint(
                [field, "framework_id", "organization_id", "language_id"],
                [
                    "course_levels.id",
                    "course_levels.framework_id",
                    "course_levels.organization_id",
                    "course_levels.language_id",
                ],
            )
            for field in ("entry_level_id", "exit_level_id")
        ],
        CheckConstraint("capacity >= 1", name="ck_class_capacity"),
        CheckConstraint("ends_on >= starts_on", name="ck_class_dates"),
        CheckConstraint("format IN ('offline', 'online', 'hybrid')", name="ck_class_format"),
        CheckConstraint("format <> 'online' OR room_id IS NULL", name="ck_online_no_room"),
        CheckConstraint("status IN ('draft', 'archived')", name="ck_class_status"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    branch_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    room_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    language_id: Mapped[UUID] = mapped_column(Uuid)
    framework_id: Mapped[UUID] = mapped_column(Uuid)
    entry_level_id: Mapped[UUID | None] = mapped_column(Uuid)
    exit_level_id: Mapped[UUID] = mapped_column(Uuid)
    course_snapshot: Mapped[dict] = mapped_column(JSON)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int]
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    format: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}
