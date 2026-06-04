from __future__ import annotations

import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


def notify_catalog_expiring(
    *,
    project_title: str,
    days_left: int,
    until_iso: str,
    curator_email: str | None = None,
) -> None:
    settings = get_settings()
    curator_line = f"Куратор цикла: {curator_email}\n" if curator_email else ""
    message = (
        f"EdAgent · каталог\n"
        f"Проект «{project_title}» скоро исчезнет из каталога.\n"
        f"Осталось дней: {days_left}\n"
        f"Дата снятия: {until_iso[:10] if until_iso else '—'}\n"
        f"{curator_line}"
        f"Продлите публикацию или переведите в постоянный режим."
    )
    _send_telegram(message, settings.telegram_bot_token, settings.telegram_chat_id)
    _send_email(
        settings.notify_email,
        subject=f"EdAgent: каталог — «{project_title[:60]}» скоро снимется",
        body=message,
        settings=settings,
    )


def notify_escalation(*, level: int, title: str, description: str) -> None:
    settings = get_settings()
    message = f"EdAgent · эскалация #{level}\n{title}\n\n{description}"
    _send_telegram(message, settings.telegram_bot_token, settings.telegram_chat_id)
    _send_email(
        settings.notify_email,
        subject=f"EdAgent: эскалация #{level}",
        body=message,
        settings=settings,
    )


def _send_telegram(text: str, token: str, chat_id: str) -> None:
    if not token or not chat_id:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        ).raise_for_status()
    except Exception as exc:
        logger.warning("telegram notify failed: %s", exc)


def _send_email(to: str, *, subject: str, body: str, settings) -> None:
    if not to or not settings.smtp_host:
        return
    try:
        from .outreach.mailer import send_email

        send_email(to=to, subject=subject, body=body)
    except Exception as exc:
        logger.warning("email notify failed: %s", exc)
