from __future__ import annotations

import logging
from typing import Any

import httpx

from ..hh_cache import cached_json_get

logger = logging.getLogger(__name__)

HH_API = "https://api.hh.ru"


class HeadHunterClient:
    def __init__(self, user_agent: str, access_token: str = ""):
        self.user_agent = user_agent
        self.access_token = access_token.strip()

    def _headers(self) -> dict[str, str]:
        h = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def search_vacancies(
        self,
        *,
        text: str,
        area_id: str | None = None,
        per_page: int = 50,
        max_pages: int = 2,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 0

        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            while page < max_pages:
                params: dict[str, Any] = {
                    "text": text,
                    "per_page": min(per_page, 100),
                    "page": page,
                }
                if area_id:
                    params["area"] = area_id

                payload = cached_json_get(client, f"{HH_API}/vacancies", params=params)
                items = payload.get("items") or []
                if not items:
                    break

                for item in items:
                    vid = item.get("id")
                    if not vid:
                        continue
                    detail = self._fetch_vacancy(client, str(vid))
                    if detail:
                        results.append(detail)
                    else:
                        results.append(item)

                page += 1
                if page >= payload.get("pages", page + 1):
                    break

        logger.info("HH collected %d vacancies for query=%r", len(results), text)
        return results

    def _fetch_vacancy(self, client: httpx.Client, vacancy_id: str) -> dict[str, Any] | None:
        try:
            return cached_json_get(client, f"{HH_API}/vacancies/{vacancy_id}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            logger.warning("HH vacancy %s failed: %s", vacancy_id, exc)
            return None
        except httpx.HTTPError as exc:
            logger.warning("HH vacancy %s failed: %s", vacancy_id, exc)
            return None

    @staticmethod
    def vacancy_text(vacancy: dict[str, Any]) -> str:
        from .skills import vacancy_text_from_dict

        return vacancy_text_from_dict(vacancy)
