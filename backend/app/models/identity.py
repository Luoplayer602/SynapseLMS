from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.expressions import EmailKey

ROLE_NAMES = ("organization_manager", "staff", "teacher", "student")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_root_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        return value.strip().lower()


# Also protect writes that bypass the ORM. Existing email values remain unchanged.
Index("uq_users_email_normalized", EmailKey(User.email), unique=True)


class UserMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_memberships"
    __table_args__ = (
        CheckConstraint(
            "NOT is_active OR ended_at IS NULL",
            name="ck_user_memberships_active_not_ended",
        ),
        CheckConstraint(
            "role IN ('organization_manager', 'staff', 'teacher', 'student')",
            name="ck_user_memberships_role",
        ),
        Index(
            "uq_user_memberships_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
