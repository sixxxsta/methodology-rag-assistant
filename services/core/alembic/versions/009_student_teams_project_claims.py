"""009 — student teams, project team claims, max_teams on projects

Revision ID: 009_student_teams_project_claims
Revises: 008_curator_scope_catalog_ttl
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_student_teams_project_claims"
down_revision: Union[str, None] = "008_curator_scope_catalog_ttl"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("max_teams", sa.Integer(), server_default="3", nullable=False),
    )
    op.create_table(
        "student_teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("leader_email", sa.String(length=255), nullable=False),
        sa.Column("invite_code", sa.String(length=32), nullable=False),
        sa.Column("max_members", sa.Integer(), server_default="6", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_student_teams_leader_email", "student_teams", ["leader_email"])
    op.create_index("ix_student_teams_invite_code", "student_teams", ["invite_code"], unique=True)

    op.create_table(
        "student_team_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("student_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_email", sa.String(length=255), nullable=False),
        sa.Column("student_user_id", sa.String(length=64), nullable=True),
        sa.Column("is_leader", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_student_team_members_team_id", "student_team_members", ["team_id"])
    op.create_index("ix_student_team_members_student_email", "student_team_members", ["student_email"])
    op.create_unique_constraint(
        "uq_student_team_members_team_email",
        "student_team_members",
        ["team_id", "student_email"],
    )

    op.create_table(
        "project_team_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("student_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leader_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_project_team_claims_project_id", "project_team_claims", ["project_id"])
    op.create_index("ix_project_team_claims_team_id", "project_team_claims", ["team_id"])

    op.add_column(
        "project_enrollments",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("student_teams.id"), nullable=True),
    )
    op.create_index("ix_project_enrollments_team_id", "project_enrollments", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_project_enrollments_team_id", table_name="project_enrollments")
    op.drop_column("project_enrollments", "team_id")
    op.drop_table("project_team_claims")
    op.drop_table("student_team_members")
    op.drop_table("student_teams")
    op.drop_column("projects", "max_teams")
