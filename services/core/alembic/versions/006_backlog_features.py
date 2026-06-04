"""006 — comm versions, email outbox, student profiles

Revision ID: 006_backlog_features
Revises: 005_strategy_memory
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_backlog_features"
down_revision: Union[str, None] = "005_strategy_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "communication_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("communication_id", sa.Integer(), sa.ForeignKey("communications.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("value_proposition", sa.Text(), nullable=True),
        sa.Column("edited_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_communication_versions_comm_id",
        "communication_versions",
        ["communication_id"],
    )

    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("communication_id", sa.Integer(), sa.ForeignKey("communications.id"), nullable=False),
        sa.Column("to_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_email_outbox_status", "email_outbox", ["status"])

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("skills", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("student_profiles")
    op.drop_index("ix_email_outbox_status", table_name="email_outbox")
    op.drop_table("email_outbox")
    op.drop_index("ix_communication_versions_comm_id", table_name="communication_versions")
    op.drop_table("communication_versions")
