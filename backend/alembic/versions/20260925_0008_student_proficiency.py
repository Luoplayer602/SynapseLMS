"""Student proficiency and immutable history; no student data is backfilled."""

import sqlalchemy as sa

from alembic import op

revision = "20260925_0008"
down_revision = "20260924_0007"
branch_labels = None
depends_on = None


def shared():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("language_id", sa.Uuid(), nullable=False),
        sa.Column("framework_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        *[sa.Column(n, sa.Uuid()) for n in ("self_level_id", "verified_level_id", "goal_level_id")],
        *[
            sa.Column(n, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
            for n in ("created_at", "updated_at")
        ],
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
            for n in ("self_level_id", "verified_level_id", "goal_level_id")
        ],
    ]


def upgrade():
    op.create_index(
        "uq_student_profile_id_org", "student_profiles", ["id", "organization_id"], unique=True
    )
    op.create_table(
        "student_proficiencies",
        *shared(),
        sa.Column("student_profile_id", sa.Uuid(), nullable=False),
        sa.Column("self_declared_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verified_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("verification_source", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("goal_text", sa.Text(), nullable=False),
        sa.Column("target_date", sa.Date()),
        sa.Column("goals_updated_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["student_profile_id", "organization_id"],
            ["student_profiles.id", "student_profiles.organization_id"],
        ),
        sa.ForeignKeyConstraint(
            ["framework_id", "organization_id", "language_id"],
            [
                "level_frameworks.id",
                "level_frameworks.organization_id",
                "level_frameworks.language_id",
            ],
        ),
        sa.UniqueConstraint("student_profile_id", "framework_id"),
        sa.UniqueConstraint("id", "organization_id", "framework_id", "language_id"),
        sa.CheckConstraint("version >= 1", name="ck_proficiency_version"),
        sa.CheckConstraint(
            "(verified_level_id IS NULL AND verified_at IS NULL AND verified_by IS NULL) OR "
            "(verified_level_id IS NOT NULL AND verified_at IS NOT NULL "
            "AND verified_by IS NOT NULL)",
            name="ck_proficiency_verification",
        ),
    )
    op.create_table(
        "proficiency_history",
        *shared(),
        sa.Column("proficiency_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("public_snapshot", sa.JSON(), nullable=False),
        sa.Column("internal_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proficiency_id", "organization_id", "framework_id", "language_id"],
            [
                "student_proficiencies.id",
                "student_proficiencies.organization_id",
                "student_proficiencies.framework_id",
                "student_proficiencies.language_id",
            ],
        ),
        sa.UniqueConstraint("proficiency_id", "version"),
    )
    for table, fields in (
        ("student_proficiencies", ("organization_id", "student_profile_id")),
        ("proficiency_history", ("organization_id", "proficiency_id")),
    ):
        for field in fields:
            op.create_index(f"ix_{table}_{field}", table, [field])


def downgrade():
    op.drop_table("proficiency_history")
    op.drop_table("student_proficiencies")
    op.drop_index("uq_student_profile_id_org", table_name="student_profiles")
