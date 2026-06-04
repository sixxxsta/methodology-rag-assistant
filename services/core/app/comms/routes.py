from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent
from .service import (
    approve_all_ready,
    approve_communication,
    generate_batch,
    generate_faq,
    generate_letter,
    get_communication_versions,
    get_faq,
    list_for_shortlist,
    update_communication,
)
from .presentation import build_presentation_pdf

router = APIRouter(prefix="/comms", tags=["comms"])


class GenerateLetterIn(BaseModel):
    tone: Literal["formal", "informal"] = "formal"


class BatchGenerateIn(BaseModel):
    tone: Literal["formal", "informal"] = "formal"


class UpdateCommIn(BaseModel):
    subject: str | None = None
    body: str | None = None
    value_proposition: str | None = None


@router.get("/faq")
def get_faq_route(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    faq = get_faq(db)
    return {"faq": faq}


@router.get("/presentation.pdf")
def presentation_pdf(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    try:
        pdf_bytes = build_presentation_pdf(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="procompetencies_presentation.pdf"'},
    )


@router.get("/shortlist")
def shortlist_comms(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"items": list_for_shortlist(db)}


@router.post("/companies/{company_id}/generate")
def gen_letter(
    company_id: int,
    body: GenerateLetterIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return generate_letter(
            db, company_id, actor_email=user["email"], tone=body.tone
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate-batch")
def gen_batch(
    body: BatchGenerateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return generate_batch(db, actor_email=user["email"], tone=body.tone)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/faq/generate")
def gen_faq(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return generate_faq(db, actor_email=user["email"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/{comm_id}")
def patch_comm(
    comm_id: int,
    body: UpdateCommIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return update_communication(
            db,
            comm_id,
            actor_email=user["email"],
            subject=body.subject,
            body=body.body,
            value_proposition=body.value_proposition,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{comm_id}/approve")
def approve(
    comm_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return approve_communication(db, comm_id, actor_email=user["email"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/phase/complete")
def phase_complete(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return approve_all_ready(db, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{comm_id}/versions")
def comm_versions(
    comm_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    try:
        return {"versions": get_communication_versions(db, comm_id)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
