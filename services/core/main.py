from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.middleware import CorrelationIdMiddleware
from app.outreach.public_routes import router as outreach_public_router
from app.routes import router
from app.startup_checks import validate_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title="EdAgent Core", version="0.1.0", description="Workflow, phases, audit")
app.add_middleware(CorrelationIdMiddleware)
app.include_router(router)
app.include_router(outreach_public_router, prefix="/api")

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    validate_settings(get_settings())
    init_db()
    from app.competency.service import seed_program_competencies
    from app.cycles.service import ensure_default_cycle, ensure_workspace
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        bootstrap_user = {"email": "admin@example.com", "role": "admin"}
        ws = ensure_workspace(db)
        cycle = ensure_default_cycle(db, ws, bootstrap_user)
        seed_program_competencies(db, ws.id, cycle_id=cycle.id)
    finally:
        db.close()
    logger.info("Core DB initialized")
