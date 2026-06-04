from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

SKILL_ALIASES: dict[str, list[str]] = {
    "Python": [r"\bpython\b", r"\bпитон\b"],
    "Java": [r"\bjava\b(?!\s*script)", r"\bджава\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\btypescript\b", r"\bts\b"],
    "React": [r"\breact\b", r"\breactjs\b", r"\bnext\.?js\b"],
    "Vue": [r"\bvue\b", r"\bvuejs\b"],
    "SQL": [r"\bsql\b", r"\bpostgresql\b", r"\bpostgres\b", r"\bmysql\b"],
    "Git": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    "Docker": [r"\bdocker\b", r"\bконтейнер"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Agile": [r"\bagile\b", r"\bаджайл\b"],
    "Scrum": [r"\bscrum\b", r"\bскрам\b"],
    "Kanban": [r"\bkanban\b", r"\bканбан\b"],
    "DevOps": [r"\bdevops\b", r"\bдевопс\b"],
    "CI/CD": [r"\bci/?cd\b", r"\bнепрерывн"],
    "REST API": [r"\brest\b", r"\brestful\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "Linux": [r"\blinux\b", r"\bлинукс\b"],
    "Тестирование": [r"\bтестирован", r"\bpytest\b", r"\bjunit\b", r"\bqa\b"],
    "Машинное обучение": [r"\bml\b", r"\bmachine learning\b", r"\bмашинн", r"\bнейросет"],
    "Аналитика данных": [r"\bdata analyst", r"\banalyst\b", r"\bаналитик данных", r"\bpandas\b"],
    "Коммуникации": [r"\bкоммуник", r"\bcommunication"],
    "Работа в команде": [r"\bкоманд", r"\bteam"],
    "Документирование": [r"\bдокумент", r"\bdocumentation"],
    "UML": [r"\buml\b"],
    "Микросервисы": [r"\bмикросервис", r"\bmicroservice"],
    "Безопасность": [r"\bsecurity\b", r"\bбезопасност", r"\bowasp\b"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b"],
    "Redis": [r"\bredis\b"],
    "C#": [r"\bc#\b", r"\bc sharp\b", r"\b\.net\b"],
    "Golang": [r"\bgolang\b"],
    "Project Management": [r"\bproject manager", r"\bуправлени[ея] проект"],
    "Figma": [r"\bfigma\b"],
    "Excel": [r"\bexcel\b", r"\bэксель\b"],
}


@dataclass(frozen=True)
class SkillHit:
    name: str
    count: int


def normalize_skill_label(raw: str) -> str | None:
    name = raw.strip()
    if not name or len(name) < 2:
        return None
    lowered = name.lower()
    for canonical, patterns in SKILL_ALIASES.items():
        if canonical.lower() == lowered:
            return canonical
        for pattern in patterns:
            if re.search(pattern, lowered, re.IGNORECASE):
                return canonical
    if len(name) > 48:
        return None
    return name[:128]


def extract_skills(text: str) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    found: list[str] = []
    for canonical, patterns in SKILL_ALIASES.items():
        for pattern in patterns:
            if re.search(pattern, lowered, re.IGNORECASE):
                found.append(canonical)
                break
    return found


def extract_skills_from_vacancy(vacancy: dict[str, Any]) -> list[str]:
    found: set[str] = set()
    for item in vacancy.get("key_skills") or []:
        if isinstance(item, dict) and item.get("name"):
            label = normalize_skill_label(str(item["name"]))
            if label:
                found.add(label)
    for skill in extract_skills(vacancy_text_from_dict(vacancy)):
        found.add(skill)
    return sorted(found)


def vacancy_text_from_dict(vacancy: dict[str, Any]) -> str:
    parts = [vacancy.get("name") or "", vacancy.get("description") or ""]
    snippet = vacancy.get("snippet") or {}
    if isinstance(snippet, dict):
        parts.append(snippet.get("requirement") or "")
        parts.append(snippet.get("responsibility") or "")
    return "\n".join(p for p in parts if p)


def aggregate_skill_counts(texts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in texts:
        for skill in extract_skills(text):
            counts[skill] = counts.get(skill, 0) + 1
    return counts


def aggregate_skill_counts_weighted(vacancies: list[dict[str, Any]]) -> dict[str, int]:
    """TF-IDF-inspired demand scores 0–100 from vacancy documents."""
    if not vacancies:
        return {}

    doc_skills: list[set[str]] = []
    total_counts: dict[str, int] = {}
    for vacancy in vacancies:
        skills = set(extract_skills_from_vacancy(vacancy))
        doc_skills.append(skills)
        for skill in skills:
            total_counts[skill] = total_counts.get(skill, 0) + 1

    n_docs = len(doc_skills)
    doc_freq = {skill: 0 for skill in total_counts}
    for skills in doc_skills:
        for skill in skills:
            doc_freq[skill] += 1

    weighted: dict[str, float] = {}
    for skill, count in total_counts.items():
        df = doc_freq.get(skill, 1)
        tf = count / n_docs
        idf = math.log((n_docs + 1) / df)
        weighted[skill] = tf * idf * count

    if not weighted:
        return {}

    max_score = max(weighted.values()) or 1.0
    return {
        skill: min(100, int(round(score / max_score * 100)))
        for skill, score in weighted.items()
    }
