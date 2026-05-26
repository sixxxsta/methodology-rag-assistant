from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def is_hh_user_agent_rejected(user_agent: str) -> bool:
    ua = user_agent.lower()
    return "example.com" in ua or "test@" in ua or len(user_agent.strip()) < 10


def hh_error_hint(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
            errors = payload.get("errors") or []
            for err in errors:
                if err.get("type") == "bad_user_agent":
                    return (
                        "HeadHunter отклонил User-Agent. Укажите в .env реальный email: "
                        "HH_USER_AGENT=EdAgent/1.0 (you@urfu.ru). "
                        "Пока используются демо-данные."
                    )
        except Exception:
            pass
        return f"HeadHunter API: HTTP {exc.response.status_code}. Используются демо-данные."
    return f"{exc}. Используются демо-данные."


def load_demo_vacancies(query: str) -> list[dict[str, Any]]:
    path = DATA_DIR / "demo_vacancies.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for i, item in enumerate(items):
        out.append(
            {
                "id": f"demo-vac-{i}",
                "name": f"{item['title']} ({query})",
                "description": item["body"],
                "key_skills": [{"name": s.strip()} for s in item["body"].split(",")[:6]],
            }
        )
    logger.warning("Using %d demo vacancies (HH unavailable)", len(out))
    return out


def load_demo_employers() -> list[dict[str, Any]]:
    path = DATA_DIR / "demo_employers.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    logger.warning("Using %d demo employers (HH unavailable)", len(items))
    return items
