from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from .tracking import (
    TRANSPARENT_GIF,
    apply_delivery_event,
    mark_opened_by_token,
    parse_sendgrid_events,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/outreach", tags=["outreach-public"])


class GenericEmailEventIn(BaseModel):
    event: str
    comm_id: int | None = None
    tracking_token: str | None = None


def _verify_webhook_secret(
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
) -> None:
    secret = get_settings().email_webhook_secret.strip()
    if not secret:
        return
    if x_webhook_secret != secret:
        raise HTTPException(status_code=401, detail="invalid webhook secret")


@router.get("/track/open/{token}")
def track_open(token: str, db: Session = Depends(get_db)) -> Response:
    mark_opened_by_token(db, token)
    return Response(content=TRANSPARENT_GIF, media_type="image/gif")


@router.post("/webhooks/email")
async def email_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_webhook_secret),
) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc

    processed: list[dict] = []

    if isinstance(payload, list):
        for item in parse_sendgrid_events(payload):
            result = apply_delivery_event(
                db,
                event_type=item["event_type"],
                comm_id=item["comm_id"],
                tracking_token=item["tracking_token"],
                provider="sendgrid",
                raw=item["raw"],
            )
            if result:
                processed.append(result)
    elif isinstance(payload, dict):
        if "event" in payload:
            body = GenericEmailEventIn.model_validate(payload)
            result = apply_delivery_event(
                db,
                event_type=body.event,
                comm_id=body.comm_id,
                tracking_token=body.tracking_token,
                provider="generic",
                raw=payload,
            )
            if result:
                processed.append(result)
        else:
            events = payload.get("events") or []
            for item in parse_sendgrid_events(events if isinstance(events, list) else []):
                result = apply_delivery_event(
                    db,
                    event_type=item["event_type"],
                    comm_id=item["comm_id"],
                    tracking_token=item["tracking_token"],
                    provider="sendgrid",
                    raw=item["raw"],
                )
                if result:
                    processed.append(result)

    return {"processed": len(processed), "results": processed}
