"""Append-only enrollment decisions and financial settlements."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.admissions import Enrollment, tenant_key


class EnrollmentPeriod(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enrollment_periods"
    __table_args__ = (
        tenant_key("enrollment_id", "enrollments"),
        CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_period_range"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    enrollment_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EnrollmentOperation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "enrollment_operations"
    __table_args__ = (tenant_key("request_id", "admission_requests"),)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    request_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    session_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("class_sessions.id"))
    action: Mapped[str] = mapped_column(String(16))
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSON)


@event.listens_for(Enrollment, "after_insert")
def initial_period(_mapper, connection, enrollment):
    connection.execute(
        EnrollmentPeriod.__table__.insert().values(
            id=uuid4(),
            organization_id=enrollment.organization_id,
            enrollment_id=enrollment.id,
            starts_at=enrollment.effective_at,
        )
    )


class RefundPolicy(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refund_policies"
    __table_args__ = (
        CheckConstraint(
            "value >= 0 AND ((kind = 'fixed' AND value <= 1000000000) "
            "OR (kind = 'percent' AND value <= 100))",
            name="ck_refund_policy",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int]


class RefundCase(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refund_cases"
    __table_args__ = (
        tenant_key("request_id", "admission_requests"),
        tenant_key("invoice_id", "invoices"),
        UniqueConstraint("id", "organization_id"),
        # NULL for unapproved cases; only one positive settlement per request.
        UniqueConstraint("settled_request_id"),
        CheckConstraint(
            "proposed >= 0 AND approved >= 0 AND offset_amount >= 0 AND cash_amount >= 0 "
            "AND approved = offset_amount + cash_amount",
            name="ck_refund_amounts",
        ),
        CheckConstraint(
            "status IN ('proposed','rejected','cancelled','no_refund','pending','paid')",
            name="ck_refund_status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    invoice_id: Mapped[UUID] = mapped_column(Uuid)
    settled_request_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("admission_requests.id")
    )
    status: Mapped[str] = mapped_column(String(16), default="proposed")
    version: Mapped[int] = mapped_column(default=1)
    proposed: Mapped[int] = mapped_column(BigInteger)
    approved: Mapped[int] = mapped_column(BigInteger, default=0)
    offset_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    cash_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    snapshot: Mapped[dict] = mapped_column(JSON)
    source_digest: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(500), default="")
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class InvoiceAdjustment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "invoice_adjustments"
    __table_args__ = (
        tenant_key("invoice_id", "invoices"),
        tenant_key("case_id", "refund_cases"),
        UniqueConstraint("case_id"),
        CheckConstraint("amount > 0", name="ck_adjustment_positive"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    invoice_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    case_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[int] = mapped_column(BigInteger)


class RefundDisbursement(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refund_disbursements"
    __table_args__ = (
        tenant_key("case_id", "refund_cases"),
        UniqueConstraint("case_id"),
        CheckConstraint("amount > 0", name="ck_disbursement_positive"),
        CheckConstraint("method IN ('cash','transfer')", name="ck_disbursement_method"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"))
    case_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(12))
    reference: Mapped[str] = mapped_column(String(200))
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
