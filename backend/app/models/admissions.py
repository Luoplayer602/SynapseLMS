"""Admissions and financial records. Amounts are integer VND, never floats."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
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


def tenant_key(field, table):
    return ForeignKeyConstraint(
        [field, "organization_id"], [f"{table}.id", f"{table}.organization_id"]
    )


class AdmissionSettings(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admission_settings"
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), unique=True)
    block_debt: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)


class FeePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fee_policies"
    __table_args__ = (
        tenant_key("course_id", "courses"),
        UniqueConstraint("course_id"),
        CheckConstraint("amount >= 0", name="ck_fee_amount"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid)
    amount: Mapped[int] = mapped_column(BigInteger)
    installments: Mapped[list] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)


class DiscountCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "discount_codes"
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        tenant_key("course_id", "courses"),
        CheckConstraint(
            "value > 0 AND max_uses >= 1 AND used >= 0 AND used <= max_uses",
            name="ck_discount_limits",
        ),
        CheckConstraint("kind IN ('fixed', 'percent')", name="ck_discount_kind"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    course_id: Mapped[UUID | None] = mapped_column(Uuid)
    code: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[int] = mapped_column(BigInteger)
    starts_on: Mapped[date]
    ends_on: Mapped[date]
    max_uses: Mapped[int]
    used: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)


class AdmissionOpening(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "admission_openings"
    __table_args__ = (tenant_key("class_id", "learning_classes"), UniqueConstraint("class_id"))
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    enabled: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)


class AdmissionRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admission_requests"
    __table_args__ = (
        tenant_key("student_id", "student_profiles"),
        tenant_key("course_id", "courses"),
        tenant_key("branch_id", "branches"),
        UniqueConstraint("id", "organization_id"),
        CheckConstraint(
            "status IN ('submitted', 'rejected', 'waiting', 'placed')", name="ck_admission_status"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    course_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    branch_id: Mapped[UUID | None] = mapped_column(Uuid)
    format: Mapped[str] = mapped_column(String(16), default="any")
    availability: Mapped[list] = mapped_column(JSON)
    discount_code: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    reason: Mapped[str] = mapped_column(String(500), default="")
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(default=1)


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        tenant_key("request_id", "admission_requests"),
        tenant_key("student_id", "student_profiles"),
        tenant_key("class_id", "learning_classes"),
        UniqueConstraint("request_id"),
        UniqueConstraint("student_id", "class_id"),
        UniqueConstraint("id", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    student_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    version: Mapped[int] = mapped_column(default=1, server_default="1")


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        tenant_key("request_id", "admission_requests"),
        tenant_key("student_id", "student_profiles"),
        UniqueConstraint("request_id"),
        UniqueConstraint("id", "organization_id"),
        CheckConstraint(
            "gross >= 0 AND discount >= 0 AND discount <= gross AND total = gross - discount",
            name="ck_invoice_amounts",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    request_id: Mapped[UUID] = mapped_column(Uuid)
    student_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    gross: Mapped[int] = mapped_column(BigInteger)
    discount: Mapped[int] = mapped_column(BigInteger)
    total: Mapped[int] = mapped_column(BigInteger)
    snapshot: Mapped[dict] = mapped_column(JSON)
    installments: Mapped[list] = mapped_column(JSON)


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        tenant_key("invoice_id", "invoices"),
        CheckConstraint("amount > 0", name="ck_payment_amount"),
        CheckConstraint("method IN ('cash', 'transfer')", name="ck_payment_method"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    invoice_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(12))
    reference: Mapped[str] = mapped_column(String(200), default="")
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversed_by: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    reversal_reason: Mapped[str] = mapped_column(String(500), default="")


class AttendanceSheet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance_sheets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        UniqueConstraint("session_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    class_id: Mapped[UUID] = mapped_column(Uuid)
    session_id: Mapped[UUID] = mapped_column(Uuid)
    records: Mapped[list] = mapped_column(JSON)
    finalized: Mapped[bool] = mapped_column(default=False)
    version: Mapped[int] = mapped_column(default=1)


class BusinessOperation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "business_operations"
    __table_args__ = (UniqueConstraint("organization_id", "request_key"),)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    request_key: Mapped[UUID] = mapped_column(Uuid)
    fingerprint: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    before: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", "event_key"),)
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    event_key: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[UUID] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
