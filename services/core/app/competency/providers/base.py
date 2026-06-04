from __future__ import annotations

from typing import Any, Protocol

from ..skills import vacancy_text_from_dict


class VacancyProvider(Protocol):
    name: str

    def search_vacancies(
        self,
        *,
        text: str,
        area_id: str | None = None,
        max_pages: int = 2,
    ) -> list[dict[str, Any]]: ...


def vacancy_body(vacancy: dict[str, Any]) -> str:
    return vacancy_text_from_dict(vacancy)
