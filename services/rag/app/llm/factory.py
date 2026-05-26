from __future__ import annotations

import logging

from ..config import Settings
from .base import LLMProvider
from .gigachat import GigaChatLLM
from .inference import InferenceLLM

logger = logging.getLogger(__name__)


def resolve_llm_provider(settings: Settings) -> str:
    """Выбор провайдера: inference | gigachat | auto."""
    configured = (settings.llm_provider or "auto").strip().lower()
    if configured in {"inference", "gigachat"}:
        return configured
    if configured != "auto":
        raise ValueError(
            f"unsupported LLM_PROVIDER={settings.llm_provider!r}; "
            "use inference, gigachat, or auto"
        )
    if settings.gigachat_credentials.strip():
        logger.info("LLM_PROVIDER=auto → gigachat (credentials found)")
        return "gigachat"
    logger.info("LLM_PROVIDER=auto → inference (no GigaChat credentials)")
    return "inference"


def build_llm(settings: Settings) -> tuple[LLMProvider, str]:
    provider = resolve_llm_provider(settings)
    if provider == "gigachat":
        if not settings.gigachat_credentials.strip():
            raise ValueError(
                "LLM_PROVIDER=gigachat requires GIGACHAT_CREDENTIALS in .env"
            )
        return (
            GigaChatLLM(
                settings.gigachat_credentials,
                scope=settings.gigachat_scope,
                model=settings.gigachat_model,
                verify_ssl=settings.gigachat_verify_ssl,
                timeout_seconds=min(settings.inference_timeout_seconds, 120),
            ),
            provider,
        )
    return (
        InferenceLLM(
            settings.inference_base_url,
            settings.inference_timeout_seconds,
        ),
        provider,
    )
