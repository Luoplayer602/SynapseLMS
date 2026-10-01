"""Course grading schemes and immutable class grading context."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class CourseGradingScheme(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "course_grading_schemes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["course_id", "organization_id"], ["courses.id", "courses.organization_id"]
        ),
        UniqueConstraint("id", "organization_id"),
        UniqueConstraint("organization_id", "course_id", "revision"),
        CheckConstraint("status IN ('draft','published','retired')", name="ck_scheme_status"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    revision: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}


class CourseGradingComponent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "course_grading_components"
    __table_args__ = (
        ForeignKeyConstraint(
            ["scheme_id", "organization_id"],
            ["course_grading_schemes.id", "course_grading_schemes.organization_id"],
        ),
        UniqueConstraint("scheme_id", "code"),
        CheckConstraint("weight > 0 AND weight <= 10000", name="ck_component_weight"),
        CheckConstraint("max_score > 0 AND max_score <= 10000", name="ck_component_max"),
        CheckConstraint(
            "skill IN ('listening','speaking','reading','writing','general')",
            name="ck_component_skill",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    scheme_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    skill: Mapped[str] = mapped_column(String(16))
    max_score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    weight: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)


class ClassGradebook(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "class_gradebooks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["class_id", "course_id", "organization_id"],
            [
                "learning_classes.id",
                "learning_classes.course_id",
                "learning_classes.organization_id",
            ],
        ),
        ForeignKeyConstraint(
            ["scheme_id", "organization_id"],
            ["course_grading_schemes.id", "course_grading_schemes.organization_id"],
        ),
        UniqueConstraint("class_id"),
        UniqueConstraint("id", "class_id", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid)
    scheme_id: Mapped[UUID] = mapped_column(Uuid)
    scheme_snapshot: Mapped[dict] = mapped_column(JSON)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}


class ClassGradeItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "class_grade_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["gradebook_id", "class_id", "organization_id"],
            [
                "class_gradebooks.id",
                "class_gradebooks.class_id",
                "class_gradebooks.organization_id",
            ],
        ),
        ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        UniqueConstraint("gradebook_id", "code"),
        UniqueConstraint("id", "gradebook_id", "class_id", "organization_id"),
        CheckConstraint("max_score > 0 AND max_score <= 10000", name="ck_grade_item_max"),
        CheckConstraint("weight > 0 AND weight <= 10000", name="ck_grade_item_weight"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    gradebook_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    skill: Mapped[str] = mapped_column(String(16))
    max_score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    weight: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class StudentScore(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_scores"
    __table_args__ = (
        ForeignKeyConstraint(
            ["item_id", "gradebook_id", "class_id", "organization_id"],
            [
                "class_grade_items.id",
                "class_grade_items.gradebook_id",
                "class_grade_items.class_id",
                "class_grade_items.organization_id",
            ],
        ),
        ForeignKeyConstraint(
            ["enrollment_id", "class_id", "organization_id"],
            ["enrollments.id", "enrollments.class_id", "enrollments.organization_id"],
        ),
        UniqueConstraint("item_id", "enrollment_id"),
        CheckConstraint("score >= 0 AND score <= 10000", name="ck_student_score_nonnegative"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    gradebook_id: Mapped[UUID] = mapped_column(Uuid)
    item_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    enrollment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    comment: Mapped[str] = mapped_column(String(1000), default="")
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
