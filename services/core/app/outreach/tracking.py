from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Communication
from ..services import log_action

logger = logging.getLogger(__name__)

TRANSPARENT_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00"
    b",\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)

SENDGRID_EVENT_MAP = {
    "processed": "sent",
    "delivered": "delivered",
    "open": "opened",
    "click": "opened",
    "bounce": "bounced",
    "dropped": "bounced",
    "deferred": "pending",
}


def new_tracking_token() -> str:
    return secrets.token_urlsafe(24)


def tracking_pixel_url(token: str, base_url: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/api/outreach/track/open/{token}"


def mark_opened_by_token(db: Session, token: str) -> bool:
    comm = (
        db.query(Communication)
        .filter(Communication.tracking_token == token)
        .one_or_none()
    )
    if not comm:
        return False
    now = datetime.now(timezone.utc)
    if not comm.opened_at:
        comm.opened_at = now
        comm.delivery_status = "opened"
        log_action(
            db,
            workspace_id=None,
            actor_email="system@edagent",
            action="outreach.track_open",
            entity_id=str(comm.id),
        )
        db.commit()
    return True


def apply_delivery_event(
    db: Session,
    *,
    event_type: str,
    comm_id: int | None = None,
    tracking_token: str | None = None,
    provider: str = "webhook",
    raw: dict[str, Any] | None = None,
) -> dict | None:
    comm: Communication | None = None
    if comm_id is not None:
        comm = db.query(Communication).filter(Communication.id == comm_id).one_or_none()
    elif tracking_token:
        comm = (
            db.query(Communication)
            .filter(Communication.tracking_token == tracking_token)
            .one_or_none()
        )
    if not comm:
        return None

    normalized = SENDGRID_EVENT_MAP.get(event_type.lower(), event_type.lower())
    now = datetime.now(timezone.utc)

    if normalized in ("sent", "delivered"):
        if normalized == "delivered" and not comm.delivered_at:
            comm.delivered_at = now
        if comm.delivery_status in ("pending", "sent"):
            comm.delivery_status = normalized
    elif normalized == "opened":
        if not comm.delivered_at:
            comm.delivered_at = now
        comm.opened_at = now
        comm.delivery_status = "opened"
    elif normalized == "bounced":
        comm.delivery_status = "bounced"

    log_action(
        db,
        workspace_id=None,
        actor_email="system@edagent",
        action="outreach.email_event",
        entity_id=str(comm.id),
        details=json.dumps(
            {"provider": provider, "event": normalized, "raw_event": event_type},
            ensure_ascii=False,
        ),
    )
    db.commit()
    return {
        "communication_id": comm.id,
        "delivery_status": comm.delivery_status,
        "event": normalized,
    }


def parse_sendgrid_events(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        event_type = str(item.get("event") or "")
        unique = item.get("unique_args") or item.get("custom_args") or {}
        comm_id = unique.get("comm_id")
        token = unique.get("tracking_token")
        events.append(
            {
                "event_type": event_type,
                "comm_id": int(comm_id) if comm_id else None,
                "tracking_token": str(token) if token else None,
                "raw": item,
            }
        )
    return events
