from __future__ import annotations

from ..models import Company
from ..config import get_settings


def letter_prompt(company: Company, tone: str, industry: str | None) -> str:
    settings = get_settings()
    tone_hint = (
        "формальный деловой стиль, на «Вы»"
        if tone == "formal"
        else "дружелюбный современный стиль, на «ты», но профессионально"
    )
    contact = company.contact_name or "представитель компании"
    return f"""Напиши персонализированное письмо-приглашение к партнёрству.

Программа: {settings.program_name}, УрФУ, проектное обучение студентов.
Компания: {company.name}
Отрасль: {company.industry or industry or "IT"}
Регион: {company.region or "Россия"}
Сайт: {company.website or "—"}
Описание компании: {(company.description or "")[:1500]}
Контактное лицо: {contact}

Тон: {tone_hint}

Структура:
1) Тема письма (строка "Тема: ...")
2) Обращение
3) Ценностное предложение для компании (стажёры, проекты, кадры)
4) Конкретный call-to-action (встреча 30 минут)
5) Подпись

Не выдумывай факты о компании, опирайся на описание. Пиши на русском."""


def value_prop_prompt(company: Company, industry: str | None) -> str:
    return f"""Сформулируй краткое ценностное предложение (3–5 буллетов) для компании {company.name} 
о партнёрстве с программой проектного обучения УрФУ.
Отрасль: {industry or company.industry or "IT"}
Фокус: польза для бизнеса — проекты, кадры, ESG, HR-бренд.
Только буллеты, русский язык."""


def faq_prompt(industry: str | None) -> str:
    settings = get_settings()
    return f"""Создай FAQ для потенциальных партнёров программы {settings.program_name} (УрФУ).
Отрасль фокуса: {industry or "IT"}
8–10 вопросов и ответов в формате:
Q: ...
A: ...
Темы: сроки, нагрузка на ментора, IP, отбор студентов, риски, формат встреч."""


def faq_fallback_body() -> str:
    return """Q: Сколько времени занимает проект у студентов?
A: Обычно 10–15 часов в неделю в течение одного семестра.

Q: Нужен ли ментор от компании?
A: Достаточно 1–2 часов в неделю на созвоны и приёмку результатов.

Q: Кто владеет результатами?
A: Условия обсуждаются в договоре; часто — совместное использование.

Q: Как отбираются студенты?
A: По компетенциям из ТЗ и мотивационному письму.

Q: Какие риски?
A: Куратор УрФУ сопровождает команду; этапность и критерии приёмки фиксируются в ТЗ."""


def letter_template(company: Company, tone: str, industry: str | None) -> tuple[str, str]:
    settings = get_settings()
    contact = company.contact_name or "коллеги"
    ind = company.industry or industry or "IT"
    if tone == "formal":
        body = f"""Уважаемые {contact}!

Компания {company.name} — интересный партнёр для программы {settings.program_name} (УрФУ).

Мы предлагаем формат проектного обучения: команда студентов под кураторством преподавателей решает прикладную задачу вашего бизнеса в отрасли {ind}.

Готовы обсудить тему проекта и формат взаимодействия на короткой встрече (30 минут) в удобное для вас время.

С уважением,
Команда {settings.program_name}, УрФУ"""
        subject = f"Партнёрство УрФУ × {company.name} — проект для студентов"
    else:
        body = f"""Привет, {contact}!

Мы из программы {settings.program_name} УрФУ. Смотрели профиль {company.name} — кажется, студенческий проект может быть полезен в {ind}.

Можем созвониться на 30 минут и набросать идею задачи под вашу команду?

Спасибо!
Команда {settings.program_name}"""
        subject = f"Идея студенческого проекта для {company.name}"
    return subject[:512], body


def value_prop_template(company: Company, industry: str | None) -> str:
    ind = company.industry or industry or "IT"
    return f"""• Прикладной проект под задачи {company.name} ({ind})
• Подбор студентов по компетенциям из ТЗ
• Куратор УрФУ снижает риски для ментора компании
• Возможность протестировать кандидатов в деле
• Гибкий формат: 10–15 ч/нед на стороне студентов"""


def parse_subject_body(raw: str) -> tuple[str, str]:
    text = raw.strip()
    subject = "Приглашение к партнёрству — проектное обучение УрФУ"
    if text.lower().startswith("тема:"):
        first_line, _, rest = text.partition("\n")
        subject = first_line.replace("Тема:", "").replace("тема:", "").strip() or subject
        text = rest.strip()
    return subject[:512], text
