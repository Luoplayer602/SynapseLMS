"""Email action digests, verification status and login device labels."""

import sqlalchemy as sa

from alembic import op

revision = "20260922_0004"
down_revision = "20260920_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.add_column("auth_sessions", sa.Column("user_agent", sa.String(512)))
    op.create_table(
        "account_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')", name="ck_account_purpose"
        ),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_account_hash"),
        sa.CheckConstraint("expires_at > created_at", name="ck_account_expiry"),
    )
    op.create_index("ix_account_tokens_user_id", "account_tokens", ["user_id"])


def downgrade():
    op.drop_table("account_tokens")
    op.drop_column("auth_sessions", "user_agent")
    op.drop_column("users", "email_verified_at")
