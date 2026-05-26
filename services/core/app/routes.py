from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db
from .schemas import DashboardOut, EscalationResolveIn, IndustryApproveIn, PhaseUpdateIn
from .comms.routes import router as comms_router
from .outreach.routes import router as outreach_router
from .projects.routes import router as projects_router
from .companies.routes import router as companies_router
from .competency.routes import router as competency_router
from .security import require_internal
from .services import (
    get_dashboard,
    resolve_escalation,
    seed_escalation_if_needed,
    update_phase,
    approve_industry,
)

router = APIRouter(prefix="/api")
router.include_router(competency_router)
router.include_router(companies_router)
router.include_router(comms_router)
router.include_router(outreach_router)
router.include_router(projects_router)


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "core"}


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
) -> DashboardOut:
    seed_escalation_if_needed(db)
    return get_dashboard(db)


@router.patch("/phases/{phase_key}")
def patch_phase(
    phase_key: str,
    body: PhaseUpdateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    try:
        return update_phase(
            db,
            phase_key,
            actor_email=user["email"],
            status=body.status,
            progress_pct=body.progress_pct,
            notes=body.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/escalations/{escalation_id}/resolve")
def resolve(
    escalation_id: int,
    body: EscalationResolveIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return resolve_escalation(
            db,
            escalation_id,
            actor_email=user["email"],
            status=body.status,
            comment=body.comment,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/industry/approve", response_model=DashboardOut)
def industry_approve(
    body: IndustryApproveIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return approve_industry(
        db,
        actor_email=user["email"],
        industry=body.industry,
        comment=body.comment,
    )
