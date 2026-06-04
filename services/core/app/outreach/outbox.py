from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Communication, EmailOutbox
from .mailer import send_email, smtp_configured
from .service import send_letter
from .tracking import new_tracking_token, tracking_pixel_url

logger = logging.getLogger(__name__)


def enqueue_email(
    db: Session,
    *,
    communication_id: int,
    to_email: str,
    subject: str,
    body: str,
    tracking_token: str | None,
) -> EmailOutbox:
    row = EmailOutbox(
        communication_id=communication_id,
        to_email=to_email,
        subject=subject,
        body=body,
        status="pending",
        scheduled_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.flush()
    return row


def process_outbox_batch(db: Session, *, limit: int = 20) -> dict:
    settings = get_settings()
    if not smtp_configured():
        return {"skipped": True, "reason": "smtp not configured"}

    rows = (
        db.query(EmailOutbox)
        .filter(EmailOutbox.status == "pending", EmailOutbox.attempts < settings.email_queue_max_attempts)
        .order_by(EmailOutbox.scheduled_at.asc().nullslast(), EmailOutbox.id)
        .limit(limit)
        .all()
    )

    sent = failed = 0
    for row in rows:
        comm = db.query(Communication).filter(Communication.id == row.communication_id).one_or_none()
        if not comm:
            row.status = "failed"
            row.last_error = "communication missing"
            failed += 1
            continue

        if not comm.tracking_token:
            comm.tracking_token = new_tracking_token()

        pixel = None
        if settings.outreach_tracking_base_url:
            pixel = tracking_pixel_url(comm.tracking_token, settings.outreach_tracking_base_url)

        try:
            send_email(
                to=row.to_email,
                subject=row.subject,
                body=row.body,
                tracking_pixel_url=pixel,
            )
            now = datetime.now(timezone.utc)
            row.status = "sent"
            row.sent_at = now
            comm.delivery_status = "sent"
            comm.sent_at = now
            comm.status = "sent"
            sent += 1
        except Exception as exc:
            row.attempts += 1
            row.last_error = str(exc)[:500]
            if row.attempts >= settings.email_queue_max_attempts:
                row.status = "failed"
            failed += 1
            logger.warning("outbox send %s failed: %s", row.id, exc)

    db.commit()
    return {"processed": len(rows), "sent": sent, "failed": failed}
