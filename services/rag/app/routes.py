from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .security import verify_internal_key

from .config import get_settings
from .deps import get_pipeline
from .feedback import FeedbackEntry, FeedbackStore
from .schemas import (
    ChatRequest,
    ChatResponse,
    FeedbackRequest,
    HealthResponse,
    IngestResponse,
    SourceItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()
feedback_store = FeedbackStore()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    pipeline = get_pipeline()
    pipeline.ensure_ready()
    return HealthResponse(
        status="ok",
        llm_provider_configured=settings.llm_provider,
        llm_provider_active=pipeline.llm_provider_active,
        qdrant_collection=settings.qdrant_collection,
        knowledge_points=pipeline.store.count(),
        embedding_model=settings.embedding_model,
    )


@router.get("/ready")
async def ready() -> dict:
    try:
        pipeline = get_pipeline()
        points = pipeline.store.count()
        return {
            "status": "ready",
            "qdrant_collection": settings.qdrant_collection,
            "knowledge_points": points,
            "llm_provider_active": pipeline.llm_provider_active,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    pipeline = get_pipeline()
    try:
        result = await pipeline.chat(
            request.message,
            session_id=request.session_id,
            language=request.language,
        )
        return ChatResponse(
            session_id=result["session_id"],
            answer=result["answer"],
            sources=[SourceItem(**s) for s in result["sources"]],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("chat failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/feedback")
async def feedback(request: FeedbackRequest) -> dict[str, str]:
    feedback_store.add(
        FeedbackEntry(
            session_id=request.session_id,
            rating=request.rating,
            comment=request.comment,
            question=request.question,
            answer=request.answer,
        )
    )
    return {"status": "ok"}


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(verify_internal_key)])
async def ingest() -> IngestResponse:
    pipeline = get_pipeline()
    knowledge_dir = Path(settings.knowledge_dir).resolve()
    try:
        stats = pipeline.ingest_directory(knowledge_dir)
        pipeline.ensure_ready()
        total = pipeline.store.count()
        return IngestResponse(
            files=stats["files"],
            chunks=stats["chunks"],
            collection=settings.qdrant_collection,
            total_points=total,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("ingest failed")
        raise HTTPException(status_code=500, detail="ingest failed") from exc
