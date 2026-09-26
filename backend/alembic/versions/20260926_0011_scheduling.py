"""Teacher assignments, weekly drafts and atomic confirmed sessions; no backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0011"
down_revision = "20260926_0010"
branch_labels = None
depends_on = None


def base():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("class_id", sa.Uuid(), nullable=False),
    ]


def timestamps():
    return [
        sa.Column(n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        for n in ("created_at", "updated_at")
    ]


def class_key():
    return sa.ForeignKeyConstraint(
        ["class_id", "organization_id"], ["learning_classes.id", "learning_classes.organization_id"]
    )


def teacher_key():
    return sa.ForeignKeyConstraint(
        ["teacher_profile_id", "organization_id"],
        ["teacher_profiles.id", "teacher_profiles.organization_id"],
    )


def upgrade():
    op.create_index(
        "uq_learning_class_id_org", "learning_classes", ["id", "organization_id"], unique=True
    )
    op.create_table(
        "class_teachers",
        *base(),
        sa.Column("teacher_profile_id", sa.Uuid(), nullable=False),
        sa.Column("override_reason", sa.String(500), nullable=False),
        class_key(),
        teacher_key(),
        sa.UniqueConstraint("class_id", "teacher_profile_id"),
        sa.UniqueConstraint("class_id", "teacher_profile_id", "organization_id"),
    )
    op.create_table(
        "schedule_plans",
        *base(),
        *timestamps(),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmation_key", sa.Uuid()),
        sa.Column("preview_digest", sa.String(64)),
        class_key(),
        sa.UniqueConstraint("class_id"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_plan_dates"),
    )
    op.create_table(
        "class_sessions",
        *base(),
        *timestamps(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("room_id", sa.Uuid()),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        class_key(),
        sa.ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["room_id", "branch_id", "organization_id"],
            ["rooms.id", "rooms.branch_id", "rooms.organization_id"],
        ),
        sa.UniqueConstraint("class_id", "starts_at"),
        sa.UniqueConstraint("id", "class_id", "organization_id"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_session_times"),
        sa.CheckConstraint("capacity >= 1", name="ck_session_capacity"),
        sa.CheckConstraint("format IN ('offline', 'online', 'hybrid')", name="ck_session_format"),
        sa.CheckConstraint(
            "(format = 'online' AND room_id IS NULL) OR "
            "(format <> 'online' AND room_id IS NOT NULL)",
            name="ck_session_room_format",
        ),
    )
    op.create_table(
        "session_teachers",
        *base(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_profile_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id", "class_id", "organization_id"],
            ["class_sessions.id", "class_sessions.class_id", "class_sessions.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["class_id", "teacher_profile_id", "organization_id"],
            [
                "class_teachers.class_id",
                "class_teachers.teacher_profile_id",
                "class_teachers.organization_id",
            ],
        ),
        teacher_key(),
        sa.UniqueConstraint("session_id", "teacher_profile_id"),
    )
    for table, columns in [
        ("class_teachers", ["class_id", "teacher_profile_id"]),
        ("class_sessions", ["organization_id", "class_id", "branch_id", "room_id", "starts_at"]),
        ("session_teachers", ["session_id", "teacher_profile_id"]),
    ]:
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in ("session_teachers", "class_sessions", "schedule_plans", "class_teachers"):
        op.drop_table(table)
    op.drop_index("uq_learning_class_id_org", table_name="learning_classes")
