"""Teacher profiles, explicit teaching capabilities, credentials and history. No backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20260926_0009"
down_revision = "20260925_0008"
branch_labels = None
depends_on = None


def base():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *[
            sa.Column(n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for n in ("created_at", "updated_at")
        ],
    ]


def profile():
    return [
        sa.Column("teacher_profile_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["teacher_profile_id", "organization_id"],
            ["teacher_profiles.id", "teacher_profiles.organization_id"],
        ),
    ]


def levels(table, parent, parent_column):
    op.create_table(
        table,
        sa.Column("id", sa.Uuid(), primary_key=True),
        *[
            sa.Column(n, sa.Uuid(), nullable=False)
            for n in (parent_column, "organization_id", "language_id", "framework_id", "level_id")
        ],
        sa.ForeignKeyConstraint(
            [parent_column, "organization_id", "language_id"],
            [parent + ".id", parent + ".organization_id", parent + ".language_id"],
        ),
        sa.ForeignKeyConstraint(
            ["level_id", "framework_id", "organization_id", "language_id"],
            [
                "course_levels.id",
                "course_levels.framework_id",
                "course_levels.organization_id",
                "course_levels.language_id",
            ],
        ),
        sa.UniqueConstraint(parent_column, "level_id"),
    )
    op.create_index("ix_" + table + "_" + parent_column, table, [parent_column])


def upgrade():
    op.create_table(
        "teacher_profiles",
        *base(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column("internal_notes", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "user_id"),
        sa.UniqueConstraint("id", "organization_id"),
        sa.CheckConstraint("version >= 1", name="ck_teacher_version"),
    )
    op.create_table(
        "teaching_capabilities",
        *base(),
        *profile(),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        sa.UniqueConstraint("teacher_profile_id", "language_id"),
        sa.UniqueConstraint("id", "teacher_profile_id", "organization_id"),
        sa.UniqueConstraint("id", "organization_id", "language_id"),
    )
    levels("teaching_capability_levels", "teaching_capabilities", "capability_id")
    op.create_table(
        "teacher_credentials",
        *base(),
        *profile(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("issuer", sa.String(200), nullable=False),
        sa.Column("issued_on", sa.Date()),
        sa.Column("expires_on", sa.Date()),
        sa.Column("internal_notes", sa.Text(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "teacher_profile_id", "organization_id"),
        sa.CheckConstraint(
            "issued_on IS NULL OR expires_on IS NULL OR expires_on >= issued_on",
            name="ck_teacher_credential_dates",
        ),
    )
    op.create_table(
        "teacher_history",
        *base(),
        *profile(),
        sa.Column("capability_id", sa.Uuid()),
        sa.Column("credential_id", sa.Uuid()),
        sa.Column("language_id", sa.Uuid()),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("public_snapshot", sa.JSON(), nullable=False),
        sa.Column("internal_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["capability_id", "organization_id", "language_id"],
            [
                "teaching_capabilities.id",
                "teaching_capabilities.organization_id",
                "teaching_capabilities.language_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["capability_id", "teacher_profile_id", "organization_id"],
            [
                "teaching_capabilities.id",
                "teaching_capabilities.teacher_profile_id",
                "teaching_capabilities.organization_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["credential_id", "teacher_profile_id", "organization_id"],
            [
                "teacher_credentials.id",
                "teacher_credentials.teacher_profile_id",
                "teacher_credentials.organization_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["language_id", "organization_id"],
            ["course_languages.id", "course_languages.organization_id"],
        ),
        sa.CheckConstraint(
            "(capability_id IS NOT NULL AND credential_id IS NULL "
            "AND language_id IS NOT NULL) OR "
            "(credential_id IS NOT NULL AND capability_id IS NULL AND language_id IS NULL)",
            name="ck_teacher_history_target",
        ),
        sa.UniqueConstraint("capability_id", "version"),
        sa.UniqueConstraint("credential_id", "version"),
        sa.UniqueConstraint("id", "organization_id", "language_id"),
    )
    levels("teacher_history_levels", "teacher_history", "history_id")
    for table in (
        "teacher_profiles",
        "teaching_capabilities",
        "teacher_credentials",
        "teacher_history",
    ):
        op.create_index("ix_" + table + "_organization_id", table, ["organization_id"])
        if table != "teacher_profiles":
            op.create_index("ix_" + table + "_teacher_profile_id", table, ["teacher_profile_id"])


def downgrade():
    for table in (
        "teacher_history_levels",
        "teacher_history",
        "teacher_credentials",
        "teaching_capability_levels",
        "teaching_capabilities",
        "teacher_profiles",
    ):
        op.drop_table(table)
