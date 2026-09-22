"""Add registration controls, invitations, support sessions, audit and rate limits."""

import sqlalchemy as sa

from alembic import op

revision = "20260920_0003"
down_revision = "20260920_0002"
branch_labels = None
depends_on = None


def stamps():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.add_column(
        "organizations",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "organizations",
        sa.Column("registration_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "organization_invites",
        *stamps(),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "uses >= 0 AND max_uses > 0 AND uses <= max_uses", name="ck_invite_uses"
        ),
    )
    op.create_index(
        "ix_organization_invites_organization_id", "organization_invites", ["organization_id"]
    )
    op.create_table(
        "support_sessions",
        *stamps(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("auth_session_id", sa.Uuid(), sa.ForeignKey("auth_sessions.id"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    for column in ("user_id", "auth_session_id", "organization_id"):
        op.create_index(f"ix_support_sessions_{column}", "support_sessions", [column])
    op.create_table(
        "audit_logs",
        *stamps(),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_id", sa.Uuid()),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    for column in ("actor_id", "organization_id"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])
    op.create_table(
        "auth_rate_buckets",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
    )
    op.create_index("ix_auth_rate_buckets_expires_at", "auth_rate_buckets", ["expires_at"])


def downgrade():
    for table in ("auth_rate_buckets", "audit_logs", "support_sessions", "organization_invites"):
        op.drop_table(table)
    op.drop_column("organizations", "registration_enabled")
    op.drop_column("organizations", "is_public")
