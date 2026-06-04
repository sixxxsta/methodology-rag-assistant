from __future__ import annotations

import logging

from .config import Settings

logger = logging.getLogger(__name__)


def validate_settings(settings: Settings) -> list[str]:
    warnings: list[str] = []

    if settings.core_internal_secret == "":
        warnings.append("CORE_INTERNAL_SECRET is empty — core API is open on internal routes")

    if "example.com" in settings.hh_user_agent.lower():
        warnings.append("HH_USER_AGENT contains example.com — HH API will use demo data")

    total = (
        settings.score_weight_competency
        + settings.score_weight_size
        + settings.score_weight_education
        + settings.score_weight_website
        + settings.score_weight_region
    )
    if total > 100:
        warnings.append(f"scoring weights sum to {total} (>100) — scores will be capped at 100")

    if settings.email_queue_enabled and not settings.smtp_host:
        warnings.append("EMAIL_QUEUE_ENABLED but SMTP not configured")

    for msg in warnings:
        logger.warning("startup: %s", msg)

    return warnings
