"""Email invitations: pending invitations do not create users or memberships."""

import sqlalchemy as sa

from alembic import op

revision = "20260922_0005"
down_revision = "20260922_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "membership_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_status", sa.String(16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("accepted_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.CheckConstraint(
            "role IN ('organization_manager', 'staff', 'teacher', 'student')",
            name="ck_membership_invitation_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked', 'expired')",
            name="ck_membership_invitation_status",
        ),
        sa.CheckConstraint(
            "delivery_status IN ('queued', 'sent', 'failed')",
            name="ck_membership_invitation_delivery",
        ),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_membership_invitation_hash"),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_membership_invitation_email"),
        sa.CheckConstraint("expires_at > created_at", name="ck_membership_invitation_expiry"),
        sa.CheckConstraint(
            "(status = 'accepted' AND accepted_at IS NOT NULL AND accepted_by IS NOT NULL)"
            " OR (status <> 'accepted' AND accepted_at IS NULL AND accepted_by IS NULL)",
            name="ck_membership_invitation_acceptance",
        ),
    )
    op.create_index(
        "ix_membership_invitations_organization_id", "membership_invitations", ["organization_id"]
    )
    op.create_index(
        "uq_membership_invitation_pending",
        "membership_invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade():
    op.drop_table("membership_invitations")
