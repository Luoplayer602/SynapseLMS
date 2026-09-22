"""Add authentication identity fields and refresh-session storage.

Revision ID: 20260920_0002
Revises: 20260919_0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260920_0002"
down_revision: str | None = "20260919_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fail before DDL if existing identities would collide; never merge accounts.
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text("SELECT 1 FROM users GROUP BY lower(trim(email)) HAVING count(*) > 1 LIMIT 1")
    ).first()
    if duplicate:
        raise RuntimeError("Duplicate normalized emails; resolve accounts before migration.")
    invalid_membership = connection.execute(
        sa.text("SELECT 1 FROM user_memberships WHERE is_active AND ended_at IS NOT NULL LIMIT 1")
    ).first()
    if invalid_membership:
        raise RuntimeError("Active memberships with ended_at must be resolved before migration.")

    op.add_column("users", sa.Column("display_name", sa.String(200), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True)))
    op.create_index(
        "uq_users_email_normalized", "users", [sa.text("lower(trim(email))")], unique=True
    )
    with op.batch_alter_table("user_memberships") as batch:
        batch.create_check_constraint(
            "ck_user_memberships_active_not_ended", "NOT is_active OR ended_at IS NULL"
        )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_auth_sessions_expiry"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("auth_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("token_hash"),
        sa.CheckConstraint("expires_at > created_at", name="ck_refresh_tokens_expiry"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_refresh_tokens_hash_length"),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])


def downgrade() -> None:
    op.drop_table("refresh_tokens")
    op.drop_table("auth_sessions")
    with op.batch_alter_table("user_memberships") as batch:
        batch.drop_constraint("ck_user_memberships_active_not_ended", type_="check")
    op.drop_index("uq_users_email_normalized", table_name="users")
    # Native DROP COLUMN keeps referencing memberships intact (SQLite >= 3.35).
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "display_name")
