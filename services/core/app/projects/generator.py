from __future__ import annotations

import json
import re
from pathlib import Path

from ..config import get_settings
from ..models import Company, Competency, PartnerAgreement
from .limits import clamp_team_size


def _load_program_competencies() -> list[str]:
    path = Path(__file__).resolve().parents[2] / "data" / "program_competencies.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item["name"] for item in data if isinstance(item, dict) and item.get("name")]
    except Exception:
        return []


def tz_prompt(
    company: Company,
    agreement: PartnerAgreement,
    *,
    industry: str | None,
    top_competencies: list[str],
) -> str:
    settings = get_settings()
    program_skills = _load_program_competencies()
    skills_hint = ", ".join(top_competencies[:12]) or ", ".join(program_skills[:12])
    return f"""Сформируй техническое задание (ТЗ) на студенческий проект для программы {settings.program_name} (УрФУ).

Компания-партнёр: {company.name}
Отрасль: {company.industry or industry or "IT"}
Описание компании: {(company.description or "")[:1200]}
Договорённости с партнёром:
{agreement.summary}

Релевантные компетенции программы: {skills_hint}

Формат ответа (строго markdown, на русском):

# Название проекта
(одна строка после заголовка)

## Цель и контекст
## Задачи (3–6 пунктов)
## Ожидаемые результаты
## Требуемые компетенции студентов
## Роли в команде
## Критерии приёмки
## Сроки и формат работы
## Контакты и менторство со стороны компании

В конце отдельной строкой метаданные (без markdown):
META: team_size=5; duration_weeks=12; competencies=Python, Agile, Git

Не выдумывай контакты — укажи плейсхолдеры, если данных нет."""


def humanize_spec(text: str) -> str:
    """Normalize LLM markdown for display in textarea."""
    if not text:
        return text
    t = text.replace("\\n", "\n").replace("\\t", "\t").replace("\r\n", "\n")
    t = re.sub(r"\n{3,}", "\n\n", t)
    lines = [ln.rstrip() for ln in t.split("\n")]
    return "\n".join(lines).strip()


def parse_tz_response(raw: str) -> tuple[str, str, int | None, int | None, str | None]:
    """Return title, spec_markdown, team_size, duration_weeks, competencies_csv."""
    text = raw.strip()
    meta_team: int | None = None
    meta_weeks: int | None = None
    meta_comp: str | None = None

    meta_match = re.search(
        r"^META:\s*team_size=(\d+);\s*duration_weeks=(\d+);\s*competencies=(.+)$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if meta_match:
        meta_team = clamp_team_size(int(meta_match.group(1)), default=4)
        meta_weeks = int(meta_match.group(2))
        meta_comp = meta_match.group(3).strip()
        text = text[: meta_match.start()].strip()

    title = "Студенческий проект с партнёром"
    if text.startswith("#"):
        first, _, rest = text.partition("\n")
        title = first.lstrip("#").strip() or title
        spec = rest.strip() if rest.strip() else text
    else:
        spec = text

    spec = humanize_spec(spec)
    return title, spec, meta_team, meta_weeks, meta_comp


def competencies_for_workspace(names: list[Competency], limit: int = 10) -> list[str]:
    ranked = sorted(
        names,
        key=lambda c: (c.demand_score or 0),
        reverse=True,
    )
    return [c.name for c in ranked[:limit]]
