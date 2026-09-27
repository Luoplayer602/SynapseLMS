"""Mutable individual sessions and append-only operation history; preserve reservations."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0012"
down_revision = "20260926_0011"
branch_labels = None
depends_on = None


def hold_teachers():
    # SQLite cannot rebuild a referenced parent with FK enforcement enabled.
    # Copy children without FKs, rebuild parent, then restore children/FKs.
    op.create_table(
        "_session_teachers_hold",
        *[
            sa.Column(n, sa.Uuid(), nullable=False)
            for n in ("id", "organization_id", "class_id", "session_id", "teacher_profile_id")
        ],
    )
    op.execute(
        sa.text(
            "INSERT INTO _session_teachers_hold SELECT id, organization_id, class_id, "
            "session_id, teacher_profile_id FROM session_teachers"
        )
    )
    op.drop_table("session_teachers")


def restore_teachers(legacy=False):
    constraints = [
        sa.ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["teacher_profile_id", "organization_id"],
            ["teacher_profiles.id", "teacher_profiles.organization_id"],
        ),
        sa.UniqueConstraint("session_id", "teacher_profile_id"),
    ]
    if legacy:
        constraints.append(
            sa.ForeignKeyConstraint(
                ["class_id", "teacher_profile_id", "organization_id"],
                [
                    "class_teachers.class_id",
                    "class_teachers.teacher_profile_id",
                    "class_teachers.organization_id",
                ],
            )
        )
    op.create_table(
        "session_teachers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *[
            sa.Column(n, sa.Uuid(), nullable=False)
            for n in ("organization_id", "class_id", "session_id", "teacher_profile_id")
        ],
        *constraints,
    )
    op.execute(
        sa.text(
            "INSERT INTO session_teachers SELECT id, organization_id, class_id, "
            "session_id, teacher_profile_id FROM _session_teachers_hold"
        )
    )
    op.drop_table("_session_teachers_hold")
    for col in ("session_id", "teacher_profile_id"):
        op.create_index(f"ix_session_teachers_{col}", "session_teachers", [col])


def upgrade():
    hold_teachers()
    naming = {"uq": "uq_%(table_name)s_%(column_0_name)s_%(column_1_name)s"}
    # PostgreSQL auto-names the old unnamed constraint; SQLite uses the convention.
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("class_sessions")
    old = next(x["name"] for x in constraints if x["column_names"] == ["class_id", "starts_at"])
    with op.batch_alter_table("class_sessions", naming_convention=naming) as batch:
        batch.drop_constraint(old or "uq_class_sessions_class_id_starts_at", type_="unique")
        batch.add_column(
            sa.Column("status", sa.String(16), nullable=False, server_default="scheduled")
        )
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(
            sa.Column("override_reason", sa.String(500), nullable=False, server_default="")
        )
        batch.create_check_constraint("ck_session_status", "status IN ('scheduled', 'cancelled')")
    restore_teachers()
    op.execute(
        sa.text(
            "UPDATE class_sessions SET override_reason = COALESCE("
            "(SELECT override_reason FROM class_teachers WHERE "
            "class_teachers.class_id = class_sessions.class_id "
            "AND override_reason <> '' LIMIT 1), '')"
        )
    )
    op.create_table(
        "session_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *[
            sa.Column(n, sa.Uuid(), nullable=False)
            for n in ("organization_id", "class_id", "session_id", "actor_id", "request_key")
        ],
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("before", sa.JSON(), nullable=False),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "request_key"),
        sa.UniqueConstraint("session_id", "version"),
    )
    op.create_index("ix_session_history_session_id", "session_history", ["session_id"])


def downgrade():
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM session_history")):
        raise RuntimeError("Session operations exist: restore a backup instead of losing history.")
    op.drop_table("session_history")
    hold_teachers()
    with op.batch_alter_table("class_sessions") as batch:
        batch.drop_constraint("ck_session_status", type_="check")
        batch.drop_column("override_reason")
        batch.drop_column("version")
        batch.drop_column("status")
        batch.create_unique_constraint("uq_session_class_start", ["class_id", "starts_at"])
    restore_teachers(legacy=True)
