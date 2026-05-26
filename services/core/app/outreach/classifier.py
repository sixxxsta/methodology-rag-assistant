from __future__ import annotations

from ..llm_client import generate_text

CATEGORIES = ("interest", "meeting_request", "question", "reject", "other")


def classify_response(subject: str, body: str) -> str:
    prompt = f"""Классифицируй ответ компании на приглашение к партнёрству.
Верни ОДНО слово из списка: interest, meeting_request, question, reject, other

interest — заинтересованы, хотят обсудить
meeting_request — просят встречу/звонок
question — уточняющие вопросы
reject — отказ
other — неясно

Тема: {subject}
Текст:
{body[:2000]}

Ответ (только категория):"""
    raw = generate_text(prompt).strip().lower()
    for cat in CATEGORIES:
        if cat in raw:
            return cat
    return "other"


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
