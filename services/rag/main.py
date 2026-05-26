from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routes import pipeline, router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Methodology RAG Assistant",
    version="1.0.0",
    description="RAG-ассистент по методологии проектной деятельности",
)
app.include_router(router)

origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _wait_for_qdrant(max_attempts: int = 30) -> None:
    import time

    for attempt in range(1, max_attempts + 1):
        try:
            pipeline.ensure_ready()
            return
        except Exception as exc:
            if attempt == max_attempts:
                raise
            logger.warning("Qdrant not ready (%s), retry %s/%s", exc, attempt, max_attempts)
            time.sleep(2)


@app.on_event("startup")
async def startup() -> None:
    _wait_for_qdrant()
    count = pipeline.store.count()
    logger.info("Qdrant collection %s has %d points", settings.qdrant_collection, count)

    if settings.auto_ingest_on_startup and count == 0:
        knowledge_dir = Path(settings.knowledge_dir).resolve()
        if knowledge_dir.exists():
            logger.info("Auto-ingesting knowledge from %s", knowledge_dir)
            stats = pipeline.ingest_directory(knowledge_dir)
            logger.info("Auto-ingest complete: %s", stats)
        else:
            logger.warning("Knowledge directory missing: %s", knowledge_dir)
