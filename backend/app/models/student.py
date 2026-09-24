from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StudentIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_identities"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)


class StudentProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "identity_id", name="uq_student_profile_tenant_identity"
        ),
        CheckConstraint("version >= 1", name="ck_student_profile_version"),
    )

    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    identity_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("student_identities.id"))
    full_name: Mapped[str] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(30))
    address: Mapped[str | None] = mapped_column(String(500))
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)

    __mapper_args__ = {"version_id_col": version}


class GuardianContact(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "guardian_contacts"
    __table_args__ = (
        Index(
            "uq_guardian_primary",
            "student_profile_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    student_profile_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("student_profiles.id", ondelete="CASCADE"),
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(200))
    relationship: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(320))
    is_primary: Mapped[bool] = mapped_column(default=False)
