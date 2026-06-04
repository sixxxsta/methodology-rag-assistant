from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from ...config import Settings
from ...hh_fallback import load_demo_vacancies

logger = logging.getLogger(__name__)

SUPERJOB_API = "https://api.superjob.ru/2.0"


class SuperjobVacancyProvider:
    name = "superjob"

    def __init__(self, settings: Settings):
        self._settings = settings
        self.demo_mode = False
        self.message: str | None = None

    def search_vacancies(
        self,
        *,
        text: str,
        area_id: str | None = None,
        max_pages: int = 2,
    ) -> list[dict[str, Any]]:
        app_id = self._settings.superjob_app_id.strip()
        if not app_id:
            self.demo_mode = True
            self.message = (
                "SUPERJOB_APP_ID не задан — используются демо-вакансии. "
                "Получите ключ на api.superjob.ru."
            )
            return _demo_as_superjob(text)

        headers = {"X-Api-App-Id": app_id}
        secret = self._settings.superjob_secret_key.strip()
        if secret:
            headers["X-Api-App-Key"] = secret

        results: list[dict[str, Any]] = []
        page = 0
        try:
            with httpx.Client(timeout=30.0, headers=headers) as client:
                while page < max_pages:
                    params: dict[str, Any] = {
                        "keyword": text,
                        "count": 50,
                        "page": page,
                    }
                    if area_id and area_id.isdigit():
                        params["town"] = area_id

                    resp = client.get(f"{SUPERJOB_API}/vacancies/", params=params)
                    resp.raise_for_status()
                    payload = resp.json()
                    objects = payload.get("objects") or []
                    if not objects:
                        break

                    for item in objects:
                        results.append(_normalize(item))
                    page += 1
                    total = payload.get("total") or 0
                    if page * 50 >= total:
                        break
        except Exception as exc:
            logger.warning("Superjob collect failed: %s", exc)
            self.demo_mode = True
            self.message = f"Superjob API: {exc}. Используются демо-данные."
            return _demo_as_superjob(text)

        logger.info("Superjob collected %d vacancies for query=%r", len(results), text)
        return results


def _normalize(item: dict[str, Any]) -> dict[str, Any]:
    rich = item.get("vacancyRichText") or item.get("candidat") or ""
    plain = re.sub(r"<[^>]+>", " ", str(rich))
    profession = item.get("profession") or item.get("title") or "Без названия"
    skills_raw = item.get("key_skills") or item.get("skills") or []
    key_skills: list[dict[str, str]] = []
    if isinstance(skills_raw, list):
        for s in skills_raw:
            if isinstance(s, dict) and s.get("title"):
                key_skills.append({"name": str(s["title"])})
            elif isinstance(s, str):
                key_skills.append({"name": s})

    return {
        "id": f"sj-{item.get('id')}",
        "name": profession,
        "description": plain,
        "key_skills": key_skills,
        "source": "superjob",
    }


def _demo_as_superjob(query: str) -> list[dict[str, Any]]:
    items = load_demo_vacancies(query)
    for item in items:
        item["id"] = f"sj-{item['id']}"
        item["source"] = "superjob"
    return items
