from __future__ import annotations

from ...config import Settings
from .base import VacancyProvider
from .hh_provider import HHVacancyProvider
from .superjob_provider import SuperjobVacancyProvider

PROVIDERS: dict[str, type] = {
    "hh": HHVacancyProvider,
    "superjob": SuperjobVacancyProvider,
}


def get_vacancy_provider(name: str, settings: Settings) -> VacancyProvider:
    key = (name or "hh").strip().lower()
    cls = PROVIDERS.get(key)
    if not cls:
        raise ValueError(f"unknown vacancy provider: {name}")
    return cls(settings)


def list_providers() -> list[str]:
    return sorted(PROVIDERS)
