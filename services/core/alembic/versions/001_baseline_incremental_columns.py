"""Baseline incremental schema patches

Revision ID: 001_baseline
Revises:
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BASELINE_ALTERS = [
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS external_id VARCHAR(128)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS tech_stack TEXT",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS employee_count INTEGER",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS size_category VARCHAR(32)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS has_education_program BOOLEAN DEFAULT FALSE",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_name VARCHAR(255)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_email VARCHAR(255)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_role VARCHAR(128)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS contact_phone VARCHAR(64)",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS score_breakdown TEXT",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS in_shortlist BOOLEAN DEFAULT FALSE",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS notes TEXT",
    "ALTER TABLE companies ADD COLUMN IF NOT EXISTS source VARCHAR(32) DEFAULT 'manual'",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS comm_type VARCHAR(32) DEFAULT 'letter'",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS value_proposition TEXT",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255)",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
    "ALTER TABLE communications ALTER COLUMN company_id DROP NOT NULL",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(32) DEFAULT 'pending'",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE communications ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS communication_id INTEGER",
    "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS classification VARCHAR(64)",
    "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS auto_handled BOOLEAN DEFAULT FALSE",
    "ALTER TABLE touch_points ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE touch_points ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS agreement_id INTEGER",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS spec_markdown TEXT",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS competencies TEXT",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS team_size INTEGER",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS duration_weeks INTEGER",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS catalog_visible BOOLEAN DEFAULT FALSE",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255)",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
]


def upgrade() -> None:
    for stmt in _BASELINE_ALTERS:
        op.execute(stmt)


def downgrade() -> None:
    pass
