"""005 — strategy memory patterns

Revision ID: 005_strategy_memory
Revises: 004_comm_outcomes
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_strategy_memory"
down_revision: Union[str, None] = "004_comm_outcomes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("tone", sa.String(length=32), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("pattern_text", sa.Text(), nullable=False),
        sa.Column("source_outcome_id", sa.Integer(), sa.ForeignKey("communication_outcomes.id"), nullable=True),
        sa.Column("source_communication_id", sa.Integer(), sa.ForeignKey("communications.id"), nullable=True),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_strategy_patterns_workspace_id", "strategy_patterns", ["workspace_id"])
    op.create_index("ix_strategy_patterns_category", "strategy_patterns", ["category", "tone"])


def downgrade() -> None:
    op.drop_index("ix_strategy_patterns_category", table_name="strategy_patterns")
    op.drop_index("ix_strategy_patterns_workspace_id", table_name="strategy_patterns")
    op.drop_table("strategy_patterns")
