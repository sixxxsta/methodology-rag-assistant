from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from ..config import get_settings
from ..llm_client import generate_text

logger = logging.getLogger(__name__)

CATEGORIES = ("interest", "meeting_request", "question", "reject", "other")

RULE_PATTERNS: dict[str, list[str]] = {
    "reject": [
        r"не\s+интерес",
        r"не\s+актуаль",
        r"отказ",
        r"не\s+готов",
        r"не\s+планиру",
        r"не\s+рассматрива",
        r"спам",
        r"удалите",
        r"no\s+interest",
        r"not\s+interested",
    ],
    "meeting_request": [
        r"встреч",
        r"созвон",
        r"звонок",
        r"позвон",
        r"календар",
        r"демо",
        r"call\s+me",
        r"schedule",
        r"meet",
    ],
    "interest": [
        r"интерес",
        r"готов",
        r"давайте",
        r"обсуд",
        r"сотруднич",
        r"partnership",
        r"interested",
        r"sounds\s+good",
    ],
    "question": [
        r"\?",
        r"уточн",
        r"подробн",
        r"сколько",
        r"как\s+это",
        r"что\s+име",
        r"расскаж",
        r"explain",
        r"clarif",
    ],
}


@dataclass(frozen=True)
class ClassificationResult:
    category: str
    confidence: float
    method: str


def classify_response(subject: str, body: str) -> ClassificationResult:
    settings = get_settings()
    text = f"{subject}\n{body}".strip()
    if settings.outreach_use_llm:
        llm_result = _classify_llm(subject, body)
        if llm_result:
            rules = _classify_rules(text)
            if rules.category == llm_result.category:
                return ClassificationResult(
                    category=llm_result.category,
                    confidence=min(0.98, llm_result.confidence + 0.1),
                    method="llm+rules",
                )
            if rules.confidence >= 0.75:
                return rules
            return llm_result
    return _classify_rules(text)


def _classify_rules(text: str) -> ClassificationResult:
    lowered = text.lower()
    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORIES}

    for category, patterns in RULE_PATTERNS.items():
        hits = 0
        for pattern in patterns:
            if re.search(pattern, lowered, re.IGNORECASE):
                hits += 1
        if hits:
            scores[category] = min(0.95, 0.45 + hits * 0.15)

    best_cat = max(scores, key=lambda k: scores[k])
    best_score = scores[best_cat]
    if best_score < 0.4:
        return ClassificationResult(category="other", confidence=0.35, method="rules")
    return ClassificationResult(category=best_cat, confidence=best_score, method="rules")


def _classify_llm(subject: str, body: str) -> ClassificationResult | None:
    prompt = f"""Классифицируй ответ компании на приглашение к партнёрству с университетом.
Верни ТОЛЬКО JSON без markdown:
{{"category":"<одно из: interest, meeting_request, question, reject, other>","confidence":0.0-1.0,"reason":"кратко"}}

interest — заинтересованы в сотрудничестве
meeting_request — просят встречу, звонок, созвон
question — уточняющие вопросы без явного согласия
reject — отказ, не интересно
other — неясно

Тема: {subject}
Текст:
{body[:2500]}"""

    try:
        raw = generate_text(prompt, timeout_seconds=25, allow_fallback=False)
    except Exception as exc:
        logger.warning("LLM classification failed: %s", exc)
        return None

    parsed = _parse_llm_json(raw)
    if not parsed:
        cat = _extract_category_token(raw)
        if cat:
            return ClassificationResult(category=cat, confidence=0.7, method="llm")
        return None

    category = parsed.get("category", "other")
    if category not in CATEGORIES:
        category = _extract_category_token(str(category)) or "other"
    try:
        confidence = float(parsed.get("confidence", 0.75))
    except (TypeError, ValueError):
        confidence = 0.75
    confidence = max(0.0, min(1.0, confidence))
    return ClassificationResult(category=category, confidence=confidence, method="llm")


def _parse_llm_json(raw: str) -> dict | None:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_category_token(raw: str) -> str | None:
    lowered = raw.strip().lower()
    for cat in CATEGORIES:
        if re.search(rf"\b{re.escape(cat)}\b", lowered):
            return cat
    return None


def auto_reply_for(category: str, question_body: str) -> str | None:
    if category == "reject":
        return (
            "Благодарим за ответ. Будем рады вернуться к диалогу, "
            "когда появится возможность для сотрудничества."
        )
    if category == "question":
        return (
            "Спасибо за вопрос. Кратко: программа ПроКомпетенции — это проектное обучение "
            "студентов УрФУ под кураторством преподавателей; нагрузка на ментора компании "
            "обычно 1–2 часа в неделю. Готовы обсудить детали на коротком созвоне."
        )
    return None
