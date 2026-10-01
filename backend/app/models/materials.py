"""Private, tenant-scoped learning materials and immutable curriculum releases."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
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


def scoped(field: str, table: str):
    return ForeignKeyConstraint(
        [field, "organization_id"], [f"{table}.id", f"{table}.organization_id"]
    )


class Material(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "materials"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        CheckConstraint("status IN ('draft','published','archived','withdrawn')"),
        CheckConstraint("audience IN ('students','teachers')"),
        CheckConstraint("scope IN ('library','class')"),
        scoped("class_id", "learning_classes"),
        ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    class_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid)
    creator_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    source: Mapped[str] = mapped_column(String(500), default="")
    language: Mapped[str] = mapped_column(String(32), default="")
    audience: Mapped[str] = mapped_column(String(16))
    scope: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    withdrawn_reason: Mapped[str] = mapped_column(String(500), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}


class MaterialVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_versions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        UniqueConstraint("material_id", "revision"),
        UniqueConstraint("organization_id", "request_key"),
        scoped("material_id", "materials"),
        CheckConstraint("kind IN ('pdf','image','audio','link')"),
        CheckConstraint("file_status IN ('pending_check','ready','rejected')"),
        CheckConstraint("size_bytes >= 0"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(16))
    file_status: Mapped[str] = mapped_column(String(16), default="pending_check")
    object_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    metadata_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    filename: Mapped[str] = mapped_column(String(200), default="")
    mime: Mapped[str] = mapped_column(String(80), default="")
    checksum: Mapped[str] = mapped_column(String(64), default="")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    scan_message: Mapped[str] = mapped_column(String(200), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaterialReview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_review_requests"
    __table_args__ = (scoped("material_version_id", "material_versions"),)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    material_version_id: Mapped[UUID] = mapped_column(Uuid)
    requester_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    reviewer_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reason: Mapped[str] = mapped_column(String(500), default="")


class Curriculum(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curricula"
    __table_args__ = (UniqueConstraint("id", "organization_id"),)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    author: Mapped[str] = mapped_column(String(200), default="")
    publisher: Mapped[str] = mapped_column(String(200), default="")
    edition: Mapped[str] = mapped_column(String(100), default="")
    isbn: Mapped[str] = mapped_column(String(32), default="")
    language: Mapped[str] = mapped_column(String(32), default="")
    status: Mapped[str] = mapped_column(String(16), default="draft")


class CurriculumVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "curriculum_versions"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        UniqueConstraint("curriculum_id", "revision"),
        scoped("curriculum_id", "curricula"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    curriculum_id: Mapped[UUID] = mapped_column(Uuid)
    revision: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CurriculumUnit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        scoped("curriculum_version_id", "curriculum_versions"),
        UniqueConstraint("curriculum_version_id", "position"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    curriculum_version_id: Mapped[UUID] = mapped_column(Uuid)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("curriculum_units.id"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)


class CurriculumMaterial(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "curriculum_materials"
    __table_args__ = (
        scoped("unit_id", "curriculum_units"),
        scoped("material_version_id", "material_versions"),
        UniqueConstraint("unit_id", "material_version_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    unit_id: Mapped[UUID] = mapped_column(Uuid)
    material_version_id: Mapped[UUID] = mapped_column(Uuid)
    page_hint: Mapped[str] = mapped_column(String(100), default="")
    required: Mapped[bool] = mapped_column(default=False)


class CourseCurriculum(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "course_curricula"
    __table_args__ = (
        scoped("course_id", "courses"),
        scoped("curriculum_version_id", "curriculum_versions"),
        UniqueConstraint("course_id", "curriculum_version_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    course_id: Mapped[UUID] = mapped_column(Uuid)
    curriculum_version_id: Mapped[UUID] = mapped_column(Uuid)
    primary: Mapped[bool] = mapped_column(default=False)


class ClassCurriculum(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "class_curricula"
    __table_args__ = (
        scoped("class_id", "learning_classes"),
        scoped("curriculum_version_id", "curriculum_versions"),
        UniqueConstraint("class_id", "curriculum_version_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    curriculum_version_id: Mapped[UUID] = mapped_column(Uuid)
    primary: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str] = mapped_column(String(500), default="")


class MaterialAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "material_assignments"
    __table_args__ = (
        UniqueConstraint("id", "organization_id"),
        UniqueConstraint("organization_id", "request_key"),
        scoped("material_version_id", "material_versions"),
        scoped("class_id", "learning_classes"),
        ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    material_version_id: Mapped[UUID] = mapped_column(Uuid)
    class_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid)
    request_key: Mapped[UUID] = mapped_column(Uuid)
    fingerprint: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500), default="")


class StudentMaterialGrant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "student_material_grants"
    __table_args__ = (
        scoped("assignment_id", "material_assignments"),
        scoped("enrollment_id", "enrollments"),
        UniqueConstraint("assignment_id", "enrollment_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid)
    assignment_id: Mapped[UUID] = mapped_column(Uuid)
    enrollment_id: Mapped[UUID] = mapped_column(Uuid)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaterialQuota(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "material_quotas"
    __table_args__ = (
        UniqueConstraint("organization_id"),
        CheckConstraint("quota_bytes > 0 AND quota_bytes <= 2147483648"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    quota_bytes: Mapped[int] = mapped_column(BigInteger, default=2_147_483_648)
