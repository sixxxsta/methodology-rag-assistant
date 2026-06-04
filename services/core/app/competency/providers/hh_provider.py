from __future__ import annotations

from typing import Any

from ...config import Settings
from ...hh_fallback import hh_error_hint, is_hh_user_agent_rejected, load_demo_vacancies
from ..hh_client import HeadHunterClient


class HHVacancyProvider:
    name = "hh"

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
        if is_hh_user_agent_rejected(self._settings.hh_user_agent):
            self.demo_mode = True
            self.message = (
                "В HH_USER_AGENT указан example.com — API hh.ru блокирует такой контакт. "
                "Используются демо-вакансии."
            )
            return load_demo_vacancies(text)

        client = HeadHunterClient(
            user_agent=self._settings.hh_user_agent,
            access_token=self._settings.hh_access_token,
        )
        try:
            items = client.search_vacancies(
                text=text,
                area_id=area_id or self._settings.hh_default_area_id or None,
                max_pages=max_pages,
            )
            for item in items:
                item.setdefault("source", "hh")
            return items
        except Exception as exc:
            self.demo_mode = True
            self.message = hh_error_hint(exc)
            return load_demo_vacancies(text)
