from __future__ import annotations

import re
from dataclasses import dataclass

# Словарь навыков: каноническое имя → варианты для поиска в тексте
SKILL_ALIASES: dict[str, list[str]] = {
    "Python": [r"\bpython\b", r"\bпитон\b"],
    "Java": [r"\bjava\b(?!\s*script)", r"\bджава\b"],
    "JavaScript": [r"\bjavascript\b", r"\bjs\b", r"\btypescript\b", r"\bts\b"],
    "React": [r"\breact\b", r"\breactjs\b"],
    "SQL": [r"\bsql\b", r"\bpostgresql\b", r"\bpostgres\b", r"\bmysql\b"],
    "Git": [r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"],
    "Docker": [r"\bdocker\b", r"\bконтейнер"],
    "Kubernetes": [r"\bkubernetes\b", r"\bk8s\b"],
    "Agile": [r"\bagile\b", r"\bаджайл\b"],
    "Scrum": [r"\bscrum\b", r"\bскрам\b"],
    "Kanban": [r"\bkanban\b", r"\bканбан\b"],
    "DevOps": [r"\bdevops\b", r"\bдевопс\b"],
    "CI/CD": [r"\bci/?cd\b", r"\bнепрерывн"],
    "REST API": [r"\brest\b", r"\bapi\b", r"\brestful\b"],
    "FastAPI": [r"\bfastapi\b"],
    "Django": [r"\bdjango\b"],
    "Flask": [r"\bflask\b"],
    "Linux": [r"\blinux\b", r"\bлинукс\b"],
    "Тестирование": [r"\bтестирован", r"\bpytest\b", r"\bjunit\b", r"\bqa\b"],
    "Машинное обучение": [r"\bml\b", r"\bmachine learning\b", r"\bмашинн"],
    "Аналитика данных": [r"\bdata analyst", r"\banalyst\b", r"\bаналитик данных"],
    "Коммуникации": [r"\bкоммуник", r"\bcommunication"],
    "Работа в команде": [r"\bкоманд", r"\bteam"],
    "Документирование": [r"\bдокумент", r"\bdocumentation"],
    "UML": [r"\buml\b"],
    "Микросервисы": [r"\bмикросервис", r"\bmicroservice"],
    "Безопасность": [r"\bsecurity\b", r"\bбезопасност", r"\bowasp\b"],
    "PostgreSQL": [r"\bpostgresql\b", r"\bpostgres\b"],
    "Redis": [r"\bredis\b"],
    "C#": [r"\bc#\b", r"\bc sharp\b", r"\b\.net\b"],
    "Go": [r"\bgolang\b", r"\bgo\b"],
    "Project Management": [r"\bproject manager", r"\bуправлени[ея] проект"],
}


@dataclass(frozen=True)
class SkillHit:
    name: str
    count: int


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


def aggregate_skill_counts(texts: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for text in texts:
        for skill in extract_skills(text):
            counts[skill] = counts.get(skill, 0) + 1
    return counts
