from collections.abc import Generator
from pathlib import Path

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
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _run_alembic_migrations()
    _repair_workspaces()


def _run_alembic_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    if not cfg_path.exists():
        return
    command.upgrade(Config(str(cfg_path)), "head")


def _repair_workspaces() -> None:
    from .services import ensure_phase_runs

    with SessionLocal() as db:
        from .models import Workspace

        for ws in db.query(Workspace).all():
            ensure_phase_runs(db, ws.id)
