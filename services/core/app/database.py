from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from sqlalchemy import text

    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_schema_migrations()
    _repair_workspaces()


def _repair_workspaces() -> None:
    from .services import ensure_phase_runs

    with SessionLocal() as db:
        from .models import Workspace

        for ws in db.query(Workspace).all():
            ensure_phase_runs(db, ws.id)


def _run_schema_migrations() -> None:
    """Add columns for incremental sprints."""
    from sqlalchemy import text

    alters = [
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
    ]
    comm_alters = [
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS comm_type VARCHAR(32) DEFAULT 'letter'",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS value_proposition TEXT",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS approved_by VARCHAR(255)",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
    ]
    alters.extend(comm_alters)
    alters.append(
        "ALTER TABLE communications ALTER COLUMN company_id DROP NOT NULL"
    )
    alters.extend([
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS delivery_status VARCHAR(32) DEFAULT 'pending'",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE communications ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS communication_id INTEGER",
        "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS classification VARCHAR(64)",
        "ALTER TABLE interactions ADD COLUMN IF NOT EXISTS auto_handled BOOLEAN DEFAULT FALSE",
        "ALTER TABLE touch_points ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE touch_points ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE",
    ])
    project_alters = [
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
    alters.extend(project_alters)
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
