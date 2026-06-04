"""004 — communication outcomes for agent memory

Revision ID: 004_comm_outcomes
Revises: 003_email_tracking
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_comm_outcomes"
down_revision: Union[str, None] = "003_email_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "communication_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("communication_id", sa.Integer(), sa.ForeignKey("communications.id"), nullable=True),
        sa.Column("interaction_id", sa.Integer(), sa.ForeignKey("interactions.id"), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_communication_outcomes_workspace_id", "communication_outcomes", ["workspace_id"])
    op.create_index("ix_communication_outcomes_company_id", "communication_outcomes", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_communication_outcomes_company_id", table_name="communication_outcomes")
    op.drop_index("ix_communication_outcomes_workspace_id", table_name="communication_outcomes")
    op.drop_table("communication_outcomes")
