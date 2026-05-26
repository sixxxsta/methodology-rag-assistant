from __future__ import annotations

from .config import Settings, get_settings
from .rag.pipeline import RAGPipeline

_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        settings = get_settings()
        _pipeline = RAGPipeline(settings)
    return _pipeline


def reset_pipeline() -> None:
    """Для тестов."""
    global _pipeline
    _pipeline = None
