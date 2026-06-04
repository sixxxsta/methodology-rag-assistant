from __future__ import annotations

import email
import imaplib
import logging
import re
from email.header import decode_header
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Company
from ..services import ensure_workspace
from .service import record_inbound

logger = logging.getLogger(__name__)


def imap_configured() -> bool:
    s = get_settings()
    return bool(s.imap_host and s.imap_user and s.imap_password)


def _decode_header_value(raw: str | None) -> str:
    if not raw:
        return ""
    parts: list[str] = []
    for chunk, enc in decode_header(raw):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return "".join(parts)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    return re.sub(r"<[^>]+>", " ", text)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""


def _match_company(db: Session, workspace_id: int, from_addr: str) -> Company | None:
    addr = from_addr.lower().strip()
    m = re.search(r"[\w.+-]+@[\w.-]+", addr)
    email_only = m.group(0) if m else addr
    return (
        db.query(Company)
        .filter(
            Company.workspace_id == workspace_id,
            Company.contact_email.ilike(email_only),
        )
        .first()
    )


def poll_imap_inbox(db: Session) -> dict[str, Any]:
    if not imap_configured():
        return {"skipped": True, "reason": "imap not configured"}

    settings = get_settings()
    ws = ensure_workspace(db)
    processed = 0
    matched = 0
    errors: list[str] = []

    try:
        if settings.imap_use_ssl:
            conn = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
        else:
            conn = imaplib.IMAP4(settings.imap_host, settings.imap_port)
        conn.login(settings.imap_user, settings.imap_password)
        conn.select(settings.imap_folder or "INBOX")

        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            conn.logout()
            return {"processed": 0, "matched": 0, "errors": ["search failed"]}

        ids = data[0].split() if data and data[0] else []
        for num in ids[:50]:
            try:
                status, msg_data = conn.fetch(num, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                subject = _decode_header_value(msg.get("Subject"))
                from_hdr = _decode_header_value(msg.get("From"))
                body = _extract_body(msg).strip()
                if not body:
                    continue

                company = _match_company(db, ws.id, from_hdr)
                processed += 1
                if not company:
                    errors.append(f"no company for {from_hdr}")
                    conn.store(num, "+FLAGS", "\\Seen")
                    continue

                record_inbound(
                    db,
                    company.id,
                    actor_email="imap@edagent",
                    subject=subject,
                    body=body,
                    auto_respond=True,
                )
                matched += 1
                conn.store(num, "+FLAGS", "\\Seen")
            except Exception as exc:
                errors.append(str(exc))

        conn.logout()
    except Exception as exc:
        logger.warning("IMAP poll failed: %s", exc)
        return {"processed": processed, "matched": matched, "errors": [str(exc)]}

    return {"processed": processed, "matched": matched, "errors": errors}
