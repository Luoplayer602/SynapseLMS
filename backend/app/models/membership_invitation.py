from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MembershipInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "membership_invitations"
    __table_args__ = (
        CheckConstraint(
            "role IN ('organization_manager', 'staff', 'teacher', 'student')",
            name="ck_membership_invitation_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked', 'expired')",
            name="ck_membership_invitation_status",
        ),
        CheckConstraint(
            "delivery_status IN ('queued', 'sent', 'failed')",
            name="ck_membership_invitation_delivery",
        ),
        CheckConstraint("length(token_hash) = 64", name="ck_membership_invitation_hash"),
        CheckConstraint("email = lower(trim(email))", name="ck_membership_invitation_email"),
        CheckConstraint("expires_at > created_at", name="ck_membership_invitation_expiry"),
        CheckConstraint(
            "(status = 'accepted' AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL)"
            " OR (status <> 'accepted' AND accepted_at IS NULL AND accepted_by IS NULL)",
            name="ck_membership_invitation_acceptance",
        ),
        Index(
            "uq_membership_invitation_pending",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivery_status: Mapped[str] = mapped_column(String(16), default="queued")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
