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

def _load_model_background() -> None:
    settings = service.settings
    logger.info(
        "Loading model %s (4bit=%s). /ready returns 503 until done — это нормально.",
        settings.model_name,
        settings.use_4bit,
    )
    try:
        service._get_or_load_model()
        logger.info("=== Inference READY: модель загружена, /ready → 200 ===")
    except Exception:
        logger.exception("=== Inference FAILED: не удалось загрузить модель ===")


@app.on_event("startup")
async def startup_event() -> None:
    threading.Thread(target=_load_model_background, daemon=True, name="model-loader").start()
