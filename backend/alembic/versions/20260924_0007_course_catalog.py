"""Tenant course catalogs and immutable level codes/ranks. No demo data."""

import sqlalchemy as sa

from alembic import op

revision = "20260924_0007"
down_revision = "20260923_0006"
branch_labels = None
depends_on = None


def common():
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
    op.create_table(
        "course_languages",
        *common(),
        sa.UniqueConstraint("organization_id", "code"),
        sa.UniqueConstraint("id", "organization_id"),
    )
    op.create_table(
        "level_frameworks",
        *common(),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        sa.UniqueConstraint("organization_id", "language_id", "code"),
        sa.UniqueConstraint("id", "organization_id", "language_id"),
    )
    op.create_table(
        "course_levels",
        *common(),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        sa.UniqueConstraint("organization_id", "framework_id", "code"),
        sa.UniqueConstraint("organization_id", "framework_id", "rank"),
        sa.UniqueConstraint("id", "framework_id", "organization_id", "language_id"),
        sa.CheckConstraint("rank >= 1", name="ck_course_level_rank"),
    )
    op.create_table(
        "courses",
        *common(),
        *[
            sa.Column(n, sa.Text(), nullable=False)
            for n in ("description", "objectives", "entry_requirements", "completion_requirements")
        ],
        *[
            sa.Column(n, sa.Uuid())
            for n in ("language_id", "framework_id", "entry_level_id", "exit_level_id")
        ],
        sa.Column("status", sa.String(16), nullable=False),
        sa.UniqueConstraint("organization_id", "code"),
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
                [n, "framework_id", "organization_id", "language_id"],
                [
                    "course_levels.id",
                    "course_levels.framework_id",
                    "course_levels.organization_id",
                    "course_levels.language_id",
                ],
            )
            for n in ("entry_level_id", "exit_level_id")
        ],
        sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_course_status"),
        sa.CheckConstraint(
            "framework_id IS NULL OR language_id IS NOT NULL", name="ck_course_framework_language"
        ),
        sa.CheckConstraint(
            "(entry_level_id IS NULL AND exit_level_id IS NULL) OR framework_id IS NOT NULL",
            name="ck_course_level_framework",
        ),
        sa.CheckConstraint(
            "status <> 'published' OR (language_id IS NOT NULL AND exit_level_id IS NOT NULL "
            "AND length(trim(objectives)) > 0)",
            name="ck_course_published",
        ),
    )
    for table in ("course_languages", "level_frameworks", "course_levels", "courses"):
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])


def downgrade():
    for table in ("courses", "course_levels", "level_frameworks", "course_languages"):
        op.drop_table(table)
