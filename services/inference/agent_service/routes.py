from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from .config import get_settings
from .schemas import GenerateRequest, GenerateResponse, HealthResponse, ReadyResponse
from .service import InferenceService

logger = logging.getLogger(__name__)

router = APIRouter()
service = InferenceService(get_settings())


@router.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    try:
        response_text = await service.generate(
            message=request.message,
            context=request.context,
            language=request.language,
        )
        return GenerateResponse(response=response_text)
    except ValueError as exc:
        logger.warning("Validation error during generation: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected inference error")
        raise HTTPException(status_code=500, detail="inference failed") from exc


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(**service.model_info())


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> ReadyResponse | JSONResponse:
    if not service.model_loaded:
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(status="loading", model_loaded=False).model_dump(),
        )
    return ReadyResponse(status="ready", model_loaded=True)
