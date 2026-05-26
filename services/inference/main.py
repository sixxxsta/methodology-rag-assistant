from __future__ import annotations

import logging
import threading

from fastapi import FastAPI

from agent_service.routes import router, service


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


_configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Inference Server", version="1.0.0")
app.include_router(router)

# Eager load model on startup to avoid first-request latency
@app.on_event("startup")
async def startup_event():
    """Load model on server startup to avoid 17s first-request delay."""
    logger.info("Eagerly loading model on startup...")
    threading.Thread(
        target=service._get_or_load_model,
        daemon=True
    ).start()
