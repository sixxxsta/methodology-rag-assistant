"""003 — email tracking token on communications

Revision ID: 003_email_tracking
Revises: 002_enrollment_roles
Create Date: 2026-06-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_email_tracking"
down_revision: Union[str, None] = "002_enrollment_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "communications",
        sa.Column("tracking_token", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_communications_tracking_token",
        "communications",
        ["tracking_token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_communications_tracking_token", table_name="communications")
    op.drop_column("communications", "tracking_token")
