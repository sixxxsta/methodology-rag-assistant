"""002 — project roles and student enrollments

Revision ID: 002_enrollment_roles
Revises: 001_baseline
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_enrollment_roles"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("hours_per_week", sa.Integer(), nullable=True),
        sa.Column("slots", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_project_roles_project_id", "project_roles", ["project_id"])

    op.create_table(
        "project_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("project_roles.id"), nullable=True),
        sa.Column("student_email", sa.String(length=255), nullable=False),
        sa.Column("student_user_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_project_enrollments_project_id", "project_enrollments", ["project_id"])
    op.create_index("ix_project_enrollments_student_email", "project_enrollments", ["student_email"])
    op.create_index("ix_project_enrollments_role_id", "project_enrollments", ["role_id"])
    op.create_index(
        "uq_project_enrollments_active",
        "project_enrollments",
        ["project_id", "student_email"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_project_enrollments_active", table_name="project_enrollments")
    op.drop_index("ix_project_enrollments_role_id", table_name="project_enrollments")
    op.drop_index("ix_project_enrollments_student_email", table_name="project_enrollments")
    op.drop_index("ix_project_enrollments_project_id", table_name="project_enrollments")
    op.drop_table("project_enrollments")
    op.drop_index("ix_project_roles_project_id", table_name="project_roles")
    op.drop_table("project_roles")
