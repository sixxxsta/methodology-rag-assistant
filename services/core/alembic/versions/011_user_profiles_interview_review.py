"""011 — user profiles (FIO) and curator interview review

Revision ID: 011_user_profiles_interview
Revises: 010_interview_required
Create Date: 2026-06-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_user_profiles_interview"
down_revision: Union[str, None] = "010_interview_required"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("email", sa.String(length=255), primary_key=True),
        sa.Column("fio", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="student", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "project_team_interviews",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_team_interviews",
        sa.Column("curator_email", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "project_team_interviews",
        sa.Column("curator_feedback", sa.Text(), nullable=True),
    )
    op.add_column(
        "project_team_interviews",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_team_interviews", "reviewed_at")
    op.drop_column("project_team_interviews", "curator_feedback")
    op.drop_column("project_team_interviews", "curator_email")
    op.drop_column("project_team_interviews", "submitted_at")
    op.drop_table("user_profiles")
