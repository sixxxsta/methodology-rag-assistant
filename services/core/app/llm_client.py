from __future__ import annotations

import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def generate_text(
    prompt: str,
    *,
    context: str = "",
    timeout_seconds: int | None = None,
    allow_fallback: bool = True,
) -> str:
    settings = get_settings()
    user_message = prompt
    if context:
        user_message = f"{context}\n\n---\n\n{prompt}"

    timeout = timeout_seconds if timeout_seconds is not None else settings.rag_timeout_seconds

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{settings.rag_service_url.rstrip('/')}/chat",
                json={"message": user_message, "session_id": "edagent-comms"},
            )
            resp.raise_for_status()
            data = resp.json()
            answer = (data.get("answer") or "").strip()
            if answer:
                return answer
    except Exception as exc:
        logger.warning("LLM via RAG failed: %s", exc)

    if not allow_fallback:
        raise RuntimeError("LLM unavailable")
    return _fallback_template(prompt)


def _fallback_template(prompt: str) -> str:
    return (
        "[Черновик сгенерирован без LLM — проверьте RAG/inference]\n\n"
        "Здравствуйте!\n\n"
        "УрФУ приглашает вашу компанию к сотрудничеству в рамках программы "
        "проектного обучения ПроКомпетенции. Студенты готовы выполнить прикладную "
        "задачу под кураторством преподавателей.\n\n"
        "С уважением,\nКоманда ПроКомпетенции"
    )
