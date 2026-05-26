from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_internal
from .service import (
    dashboard,
    mark_opened,
    record_agreement,
    record_inbound,
    send_followup,
    send_letter,
)

router = APIRouter(prefix="/outreach", tags=["outreach"])


class SendIn(BaseModel):
    use_smtp: bool = True


class InboundIn(BaseModel):
    subject: str = ""
    body: str
    auto_respond: bool = True


class AgreementIn(BaseModel):
    summary: str
    status: str = "agreed"


@router.get("/dashboard")
def outreach_dashboard(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    return dashboard(db)


@router.post("/communications/{comm_id}/send")
def send(
    comm_id: int,
    body: SendIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return send_letter(
            db, comm_id, actor_email=user["email"], use_smtp=body.use_smtp
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/communications/{comm_id}/opened")
def opened(
    comm_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return mark_opened(db, comm_id, actor_email=user["email"])


@router.post("/companies/{company_id}/inbound")
def inbound(
    company_id: int,
    body: InboundIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    try:
        return record_inbound(
            db,
            company_id,
            actor_email=user["email"],
            subject=body.subject,
            body=body.body,
            auto_respond=body.auto_respond,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/followups/{touch_id}/send")
def followup_send(
    touch_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return send_followup(db, touch_id, actor_email=user["email"])


@router.post("/companies/{company_id}/agreement")
def agreement(
    company_id: int,
    body: AgreementIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return record_agreement(
            db,
            company_id,
            actor_email=user["email"],
            summary=body.summary,
            status=body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
