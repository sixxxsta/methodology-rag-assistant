"""010 — interview gate and team interviews

Revision ID: 010_interview_required
Revises: 009_student_teams_project_claims
Create Date: 2026-06-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_interview_required"
down_revision: Union[str, None] = "009_student_teams_project_claims"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("interview_required", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_table(
        "project_team_interviews",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("student_teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leader_email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("questions_json", sa.Text(), nullable=True),
        sa.Column("answers_json", sa.Text(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("passed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "team_id", name="uq_project_team_interviews_project_team"),
    )
    op.create_index("ix_project_team_interviews_project_id", "project_team_interviews", ["project_id"])
    op.create_index("ix_project_team_interviews_team_id", "project_team_interviews", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_project_team_interviews_team_id", table_name="project_team_interviews")
    op.drop_index("ix_project_team_interviews_project_id", table_name="project_team_interviews")
    op.drop_table("project_team_interviews")
    op.drop_column("projects", "interview_required")
