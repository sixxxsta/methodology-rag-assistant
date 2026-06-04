"""008 — curator-owned cycles, catalog expiry on projects

Revision ID: 008_curator_scope_catalog_ttl
Revises: 007_partnership_cycles
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_curator_scope_catalog_ttl"
down_revision: Union[str, None] = "007_partnership_cycles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_partnership_cycles_created_by",
        "partnership_cycles",
        ["created_by"],
    )
    op.add_column(
        "projects",
        sa.Column("catalog_mode", sa.String(length=32), server_default="permanent", nullable=False),
    )
    op.add_column(
        "projects",
        sa.Column("catalog_visible_until", sa.DateTime(timezone=True), nullable=True),
    )
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE projects SET catalog_mode = 'permanent' WHERE catalog_visible IS TRUE"
        )
    )


def downgrade() -> None:
    op.drop_column("projects", "catalog_visible_until")
    op.drop_column("projects", "catalog_mode")
    op.drop_index("ix_partnership_cycles_created_by", table_name="partnership_cycles")
