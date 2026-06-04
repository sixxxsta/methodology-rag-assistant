from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..config import get_settings

logger = logging.getLogger(__name__)


def smtp_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def send_email(
    *,
    to: str,
    subject: str,
    body: str,
    tracking_pixel_url: str | None = None,
) -> None:
    settings = get_settings()
    if not smtp_configured():
        raise RuntimeError("SMTP not configured — use manual send")

    html_body = _html_body(body, tracking_pixel_url)
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(msg)
    logger.info("Email sent to %s", to)


def _html_body(body: str, tracking_pixel_url: str | None) -> str:
    escaped = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>\n")
    )
    pixel = ""
    if tracking_pixel_url:
        pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" alt="" />'
    return f"<html><body><div>{escaped}</div>{pixel}</body></html>"
