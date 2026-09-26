"""Branches, rooms and draft classes with course snapshots. No backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0010"
down_revision = "20260926_0009"
branch_labels = None
depends_on = None


def base():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *[
            sa.Column(n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for n in ("created_at", "updated_at")
        ],
    ]


def upgrade():
    op.create_index("uq_course_id_org", "courses", ["id", "organization_id"], unique=True)
    op.create_table(
        "branches",
        *base(),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "code"),
        sa.UniqueConstraint("id", "organization_id"),
    )
    op.create_table(
        "rooms",
        *base(),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        sa.UniqueConstraint("branch_id", "code"),
        sa.UniqueConstraint("id", "branch_id", "organization_id"),
        sa.CheckConstraint("capacity >= 1", name="ck_room_capacity"),
    )
    op.create_table(
        "learning_classes",
        *base(),
        *[
            sa.Column(n, sa.Uuid(), nullable=False)
            for n in ("course_id", "branch_id", "language_id", "framework_id", "exit_level_id")
        ],
        sa.Column("room_id", sa.Uuid()),
        sa.Column("entry_level_id", sa.Uuid()),
        sa.Column("course_snapshot", sa.JSON(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("organization_id", "code"),
        sa.ForeignKeyConstraint(
            ["course_id", "organization_id"], ["courses.id", "courses.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["branch_id", "organization_id"], ["branches.id", "branches.organization_id"]
        ),
        sa.ForeignKeyConstraint(
            ["room_id", "branch_id", "organization_id"],
            ["rooms.id", "rooms.branch_id", "rooms.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        *[
            sa.ForeignKeyConstraint(
                [field, "framework_id", "organization_id", "language_id"],
                [
                    "course_levels.id",
                    "course_levels.framework_id",
                    "course_levels.organization_id",
                    "course_levels.language_id",
                ],
            )
            for field in ("entry_level_id", "exit_level_id")
        ],
        sa.CheckConstraint("capacity >= 1", name="ck_class_capacity"),
        sa.CheckConstraint("ends_on >= starts_on", name="ck_class_dates"),
        sa.CheckConstraint("format IN ('offline', 'online', 'hybrid')", name="ck_class_format"),
        sa.CheckConstraint("format <> 'online' OR room_id IS NULL", name="ck_online_no_room"),
        sa.CheckConstraint("status IN ('draft', 'archived')", name="ck_class_status"),
    )
    for table in ("branches", "rooms", "learning_classes"):
        op.create_index("ix_" + table + "_organization_id", table, ["organization_id"])
    for table, columns in (
        ("rooms", ["branch_id"]),
        ("learning_classes", ["course_id", "branch_id", "room_id"]),
    ):
        for column in columns:
            op.create_index("ix_" + table + "_" + column, table, [column])


def downgrade():
    for table in ("learning_classes", "rooms", "branches"):
        op.drop_table(table)
    op.drop_index("uq_course_id_org", table_name="courses")
