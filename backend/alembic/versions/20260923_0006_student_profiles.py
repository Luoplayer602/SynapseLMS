"""Student identity, tenant profiles and guardian contacts; no automatic backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20260923_0006"
down_revision = "20260922_0005"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        for name in ("created_at", "updated_at")
    ]


def upgrade():
    op.create_table(
        "student_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *timestamps(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
    )
    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *timestamps(),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("identity_id", sa.Uuid(), sa.ForeignKey("student_identities.id"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("date_of_birth", sa.Date()),
        sa.Column("phone", sa.String(30)),
        sa.Column("address", sa.String(500)),
        sa.Column("internal_notes", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "identity_id", name="uq_student_profile_tenant_identity"
        ),
        sa.CheckConstraint("version >= 1", name="ck_student_profile_version"),
    )
    op.create_index("ix_student_profiles_organization_id", "student_profiles", ["organization_id"])
    op.create_table(
        "guardian_contacts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_profile_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("relationship", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_guardian_contacts_student_profile_id", "guardian_contacts", ["student_profile_id"]
    )
    op.create_index(
        "uq_guardian_primary",
        "guardian_contacts",
        ["student_profile_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        sqlite_where=sa.text("is_primary = 1"),
    )


def downgrade():
    op.drop_table("guardian_contacts")
    op.drop_table("student_profiles")
    op.drop_table("student_identities")
