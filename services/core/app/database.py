import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

logger = logging.getLogger(__name__)


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
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_alembic_migrations()
    _sync_schema_gaps()
    _repair_workspaces()


def _sync_schema_gaps() -> None:
    """Idempotent patches when ORM create_all raced ahead of Alembic stamp-and-skip."""
    from sqlalchemy import text

    patches = [
        "ALTER TABLE companies ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE competencies ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE communication_outcomes ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE strategy_patterns ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE escalations ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE phase_runs ADD COLUMN IF NOT EXISTS cycle_id INTEGER",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS catalog_mode VARCHAR(32) DEFAULT 'permanent'",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS catalog_visible_until TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS max_teams INTEGER DEFAULT 3",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS interview_required BOOLEAN DEFAULT FALSE",
        "ALTER TABLE project_team_interviews ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE project_team_interviews ADD COLUMN IF NOT EXISTS curator_email VARCHAR(255)",
        "ALTER TABLE project_team_interviews ADD COLUMN IF NOT EXISTS curator_feedback TEXT",
        "ALTER TABLE project_team_interviews ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITH TIME ZONE",
    ]
    with engine.begin() as conn:
        for stmt in patches:
            conn.execute(text(stmt))


def _run_alembic_migrations() -> None:
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    if not cfg_path.exists():
        return
    cfg = Config(str(cfg_path))
    script = ScriptDirectory.from_config(cfg)
    max_steps = len(list(script.walk_revisions())) + 2

    for _ in range(max_steps):
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        try:
            command.upgrade(cfg, "head")
            return
        except ProgrammingError as exc:
            msg = str(exc).lower()
            if "already exists" not in msg and "duplicate" not in msg:
                raise
            rev = script.get_revision(current) if current else None
            next_rev = rev.nextrev[0] if rev and rev.nextrev else None
            if not next_rev:
                logger.warning("Alembic duplicate at head, continuing: %s", exc)
                return
            logger.warning("Alembic step %s already applied via ORM, stamping %s", current, next_rev)
            command.stamp(cfg, next_rev)


def _repair_workspaces() -> None:
    from .cycles.service import ensure_default_cycle, ensure_workspace, migrate_legacy_workspace_to_cycles

    bootstrap_user = {"email": "admin@example.com", "role": "admin"}
    with SessionLocal() as db:
        ws = ensure_workspace(db)
        migrate_legacy_workspace_to_cycles(db)
        ensure_default_cycle(db, ws, bootstrap_user)
