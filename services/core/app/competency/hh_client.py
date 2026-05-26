from __future__ import annotations

import logging
from typing import Any

import httpx

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

                resp = client.get(f"{HH_API}/vacancies", params=params)
                resp.raise_for_status()
                payload = resp.json()
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
            resp = client.get(f"{HH_API}/vacancies/{vacancy_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.warning("HH vacancy %s failed: %s", vacancy_id, exc)
            return None

    @staticmethod
    def vacancy_text(vacancy: dict[str, Any]) -> str:
        parts = [
            vacancy.get("name") or "",
            vacancy.get("description") or "",
        ]
        key_skills = vacancy.get("key_skills") or []
        for ks in key_skills:
            if isinstance(ks, dict) and ks.get("name"):
                parts.append(ks["name"])
        snippet = vacancy.get("snippet") or {}
        if isinstance(snippet, dict):
            parts.append(snippet.get("requirement") or "")
            parts.append(snippet.get("responsibility") or "")
        return "\n".join(p for p in parts if p)
