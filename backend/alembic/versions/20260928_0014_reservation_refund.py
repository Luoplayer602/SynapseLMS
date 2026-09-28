"""Enrollment periods and refund ledger. Preserve old enrollment timestamps and invoices."""

from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "20260928_0014"
down_revision = "20260927_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refund_policies",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "value >= 0 AND ((kind = 'fixed' AND value <= 1000000000) "
            "OR (kind = 'percent' AND value <= 100))",
            name="ck_refund_policy",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id"),
    )
    op.create_table(
        "enrollment_operations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["request_id", "organization_id"],
            ["admission_requests.id", "admission_requests.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["class_sessions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_enrollment_operations_request_id"),
        "enrollment_operations",
        ["request_id"],
        unique=False,
    )
    op.create_table(
        "enrollment_periods",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="ck_period_range"),
        sa.ForeignKeyConstraint(
            ["enrollment_id", "organization_id"],
            ["enrollments.id", "enrollments.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_enrollment_periods_enrollment_id"),
        "enrollment_periods",
        ["enrollment_id"],
        unique=False,
    )
    op.create_table(
        "refund_cases",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("settled_request_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("proposed", sa.BigInteger(), nullable=False),
        sa.Column("approved", sa.BigInteger(), nullable=False),
        sa.Column("offset_amount", sa.BigInteger(), nullable=False),
        sa.Column("cash_amount", sa.BigInteger(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('proposed','rejected','cancelled','no_refund','pending','paid')",
            name="ck_refund_status",
        ),
        sa.CheckConstraint(
            "proposed >= 0 AND approved >= 0 AND offset_amount >= 0 AND cash_amount >= 0 "
            "AND approved = offset_amount + cash_amount",
            name="ck_refund_amounts",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "organization_id"],
            ["invoices.id", "invoices.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.ForeignKeyConstraint(
            ["request_id", "organization_id"],
            ["admission_requests.id", "admission_requests.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["settled_request_id"],
            ["admission_requests.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id"),
        sa.UniqueConstraint("settled_request_id"),
    )
    op.create_index(
        op.f("ix_refund_cases_organization_id"), "refund_cases", ["organization_id"], unique=False
    )
    op.create_table(
        "invoice_adjustments",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_adjustment_positive"),
        sa.ForeignKeyConstraint(
            ["case_id", "organization_id"],
            ["refund_cases.id", "refund_cases.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "organization_id"],
            ["invoices.id", "invoices.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_index(
        op.f("ix_invoice_adjustments_invoice_id"),
        "invoice_adjustments",
        ["invoice_id"],
        unique=False,
    )
    op.create_table(
        "refund_disbursements",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("method IN ('cash','transfer')", name="ck_disbursement_method"),
        sa.CheckConstraint("amount > 0", name="ck_disbursement_positive"),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["case_id", "organization_id"],
            ["refund_cases.id", "refund_cases.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.add_column(
        "admission_requests", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "enrollments",
        sa.Column("state", sa.String(length=16), server_default="active", nullable=False),
    )
    op.add_column(
        "enrollments", sa.Column("version", sa.Integer(), server_default="1", nullable=False)
    )
    connection = op.get_bind()
    enrollment = sa.table(
        "enrollments",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("effective_at", sa.DateTime(timezone=True)),
    )
    period = sa.table(
        "enrollment_periods",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("enrollment_id", sa.Uuid()),
        sa.column("starts_at", sa.DateTime(timezone=True)),
    )
    for row in connection.execute(sa.select(enrollment)).mappings():
        connection.execute(
            period.insert().values(
                id=uuid4(),
                organization_id=row["organization_id"],
                enrollment_id=row["id"],
                starts_at=row["effective_at"],
            )
        )


def downgrade():
    connection = op.get_bind()
    for name in (
        "enrollment_periods",
        "enrollment_operations",
        "refund_policies",
        "refund_cases",
        "invoice_adjustments",
        "refund_disbursements",
    ):
        if connection.scalar(sa.text("SELECT count(*) FROM " + name)):
            raise RuntimeError(
                "Refusing to discard lifecycle or financial data; restore a verified backup instead"
            )
    if connection.scalar(
        sa.text("SELECT count(*) FROM admission_requests WHERE cancelled_at IS NOT NULL")
    ):
        raise RuntimeError("Refusing to discard cancellation history")
    op.drop_column("enrollments", "version")
    op.drop_column("enrollments", "state")
    op.drop_column("admission_requests", "cancelled_at")
    op.drop_table("refund_disbursements")
    op.drop_index(op.f("ix_invoice_adjustments_invoice_id"), table_name="invoice_adjustments")
    op.drop_table("invoice_adjustments")
    op.drop_index(op.f("ix_refund_cases_organization_id"), table_name="refund_cases")
    op.drop_table("refund_cases")
    op.drop_index(op.f("ix_enrollment_periods_enrollment_id"), table_name="enrollment_periods")
    op.drop_table("enrollment_periods")
    op.drop_index(op.f("ix_enrollment_operations_request_id"), table_name="enrollment_operations")
    op.drop_table("enrollment_operations")
    op.drop_table("refund_policies")
