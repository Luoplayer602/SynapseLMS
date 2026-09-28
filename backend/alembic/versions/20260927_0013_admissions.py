"""Admissions, integer-VND accounting, attendance and in-app inbox. No backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20260927_0013"
down_revision = "20260926_0012"
branch_labels = None
depends_on = None


def uid(name, target=None, nullable=False):
    return sa.Column(
        name, sa.Uuid(), *([sa.ForeignKey(target)] if target else []), nullable=nullable
    )


def col(name, typ, nullable=False):
    return sa.Column(name, typ, nullable=nullable)


def key(field, table):
    return sa.ForeignKeyConstraint(
        [field, "organization_id"], [f"{table}.id", f"{table}.organization_id"]
    )


def create(name, columns, constraints=(), indexes=(), timestamps=True):
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True),
        uid("organization_id", "organizations.id"),
        *columns,
        *(
            [
                sa.Column(
                    n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
                )
                for n in ("created_at", "updated_at")
            ]
            if timestamps
            else []
        ),
        *constraints,
    )
    for field in indexes:
        op.create_index(f"ix_{name}_{field}", name, [field])


def upgrade():
    create(
        "admission_settings",
        [col("block_debt", sa.Boolean()), col("version", sa.Integer())],
        [sa.UniqueConstraint("organization_id")],
        timestamps=False,
    )
    create(
        "fee_policies",
        [
            uid("course_id"),
            col("amount", sa.BigInteger()),
            col("installments", sa.JSON()),
            col("version", sa.Integer()),
        ],
        [
            key("course_id", "courses"),
            sa.UniqueConstraint("course_id"),
            sa.CheckConstraint("amount >= 0", name="ck_fee_amount"),
        ],
        ["organization_id"],
    )
    create(
        "discount_codes",
        [
            uid("course_id", nullable=True),
            col("code", sa.String(40)),
            col("kind", sa.String(10)),
            col("value", sa.BigInteger()),
            col("starts_on", sa.Date()),
            col("ends_on", sa.Date()),
            col("max_uses", sa.Integer()),
            col("used", sa.Integer()),
            col("active", sa.Boolean()),
            col("version", sa.Integer()),
        ],
        [
            key("course_id", "courses"),
            sa.UniqueConstraint("organization_id", "code"),
            sa.CheckConstraint(
                "value > 0 AND max_uses >= 1 AND used >= 0 AND used <= max_uses",
                name="ck_discount_limits",
            ),
            sa.CheckConstraint("kind IN ('fixed', 'percent')", name="ck_discount_kind"),
        ],
        ["organization_id"],
    )
    create(
        "admission_openings",
        [uid("class_id"), col("enabled", sa.Boolean()), col("version", sa.Integer())],
        [key("class_id", "learning_classes"), sa.UniqueConstraint("class_id")],
        ["organization_id"],
        False,
    )
    create(
        "admission_requests",
        [
            uid("student_id"),
            uid("course_id"),
            uid("branch_id", nullable=True),
            col("format", sa.String(16)),
            col("availability", sa.JSON()),
            col("discount_code", sa.String(40)),
            col("status", sa.String(16)),
            col("reason", sa.String(500)),
            col("version", sa.Integer()),
        ],
        [
            key("student_id", "student_profiles"),
            key("course_id", "courses"),
            key("branch_id", "branches"),
            sa.UniqueConstraint("id", "organization_id"),
            sa.CheckConstraint(
                "status IN ('submitted', 'rejected', 'waiting', 'placed')",
                name="ck_admission_status",
            ),
        ],
        ["organization_id", "student_id", "course_id"],
    )
    create(
        "enrollments",
        [
            uid("request_id"),
            uid("student_id"),
            uid("class_id"),
            col("effective_at", sa.DateTime(timezone=True)),
        ],
        [
            key("request_id", "admission_requests"),
            key("student_id", "student_profiles"),
            key("class_id", "learning_classes"),
            sa.UniqueConstraint("request_id"),
            sa.UniqueConstraint("student_id", "class_id"),
            sa.UniqueConstraint("id", "organization_id"),
        ],
        ["organization_id", "student_id", "class_id"],
    )
    create(
        "invoices",
        [
            uid("request_id"),
            uid("student_id"),
            col("gross", sa.BigInteger()),
            col("discount", sa.BigInteger()),
            col("total", sa.BigInteger()),
            col("snapshot", sa.JSON()),
            col("installments", sa.JSON()),
        ],
        [
            key("request_id", "admission_requests"),
            key("student_id", "student_profiles"),
            sa.UniqueConstraint("request_id"),
            sa.UniqueConstraint("id", "organization_id"),
            sa.CheckConstraint(
                "gross >= 0 AND discount >= 0 AND discount <= gross AND total = gross - discount",
                name="ck_invoice_amounts",
            ),
        ],
        ["organization_id", "student_id"],
    )
    create(
        "payments",
        [
            uid("invoice_id"),
            col("amount", sa.BigInteger()),
            col("method", sa.String(12)),
            col("reference", sa.String(200)),
            uid("actor_id", "users.id"),
            col("reversed_at", sa.DateTime(timezone=True), True),
            uid("reversed_by", "users.id", True),
            col("reversal_reason", sa.String(500)),
        ],
        [
            key("invoice_id", "invoices"),
            sa.CheckConstraint("amount > 0", name="ck_payment_amount"),
            sa.CheckConstraint("method IN ('cash', 'transfer')", name="ck_payment_method"),
        ],
        ["organization_id", "invoice_id"],
    )
    create(
        "attendance_sheets",
        [
            uid("class_id"),
            uid("session_id"),
            col("records", sa.JSON()),
            col("finalized", sa.Boolean()),
            col("version", sa.Integer()),
        ],
        [
            sa.ForeignKeyConstraint(
                ["session_id", "class_id", "organization_id"],
                ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
            ),
            sa.UniqueConstraint("session_id"),
        ],
        ["organization_id"],
    )
    create(
        "business_operations",
        [
            uid("actor_id", "users.id"),
            uid("request_key"),
            col("fingerprint", sa.String(64)),
            col("action", sa.String(80)),
            uid("target_id", nullable=True),
            col("created_at", sa.DateTime(timezone=True)),
            col("before", sa.JSON()),
            col("result", sa.JSON()),
        ],
        [sa.UniqueConstraint("organization_id", "request_key")],
        ["organization_id", "target_id"],
        False,
    )
    create(
        "notifications",
        [
            uid("user_id", "users.id"),
            col("event_key", sa.String(160)),
            col("kind", sa.String(80)),
            uid("target_id"),
            col("created_at", sa.DateTime(timezone=True)),
            col("read_at", sa.DateTime(timezone=True), True),
        ],
        [sa.UniqueConstraint("organization_id", "user_id", "event_key")],
        ["organization_id", "user_id"],
        False,
    )


def downgrade():
    # No silent loss of operational/financial records on downgrade.
    names = [
        "notifications",
        "business_operations",
        "attendance_sheets",
        "payments",
        "invoices",
        "enrollments",
        "admission_requests",
        "admission_openings",
        "discount_codes",
        "fee_policies",
        "admission_settings",
    ]
    for name in names:
        if op.get_bind().scalar(sa.text(f"SELECT count(*) FROM {name}")):
            raise RuntimeError(
                "Refusing to discard admissions data; restore a verified backup instead"
            )
    for name in names:
        op.drop_table(name)
