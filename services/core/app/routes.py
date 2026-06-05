from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .profiles.service import upsert_profile
from .schemas import DashboardOut, EscalationResolveIn, IndustryApproveIn, PhaseUpdateIn
from .comms.routes import router as comms_router
from .memory.routes import router as memory_router
from .outreach.routes import router as outreach_router
from .projects.routes import router as projects_router
from .companies.routes import router as companies_router
from .competency.routes import router as competency_router
from .cycles.routes import router as cycles_router
from .teams.routes import router as teams_router
from .security import require_curator, require_edagent, require_student
from .student_data import purge_student_data
from .services import (
    get_dashboard,
    resolve_escalation,
    seed_escalation_if_needed,
    update_phase,
    approve_industry,
)

router = APIRouter(prefix="/api")
router.include_router(cycles_router)
router.include_router(teams_router)
router.include_router(competency_router)
router.include_router(companies_router)
router.include_router(comms_router)
router.include_router(memory_router)
router.include_router(outreach_router)
router.include_router(projects_router)


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "core"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    db.execute(text("SELECT 1"))
    return {"status": "ready", "service": "core", "database": "ok"}


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
) -> DashboardOut:
    seed_escalation_if_needed(db)
    return get_dashboard(db)


@router.patch("/phases/{phase_key}")
def patch_phase(
    phase_key: str,
    body: PhaseUpdateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
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
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
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
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    return approve_industry(
        db,
        actor_email=user["email"],
        industry=body.industry,
        comment=body.comment,
    )


@router.delete("/student/account-data")
def student_purge_data(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    return purge_student_data(db, student_email=user["email"])


class UserProfileIn(BaseModel):
    email: str
    fio: str = Field(min_length=2, max_length=255)
    role: str = "student"


@router.put("/internal/user-profile")
def internal_user_profile(
    body: UserProfileIn,
    db: Session = Depends(get_db),
    x_core_internal_key: str | None = Header(default=None, alias="X-Core-Internal-Key"),
):
    settings = get_settings()
    if settings.core_internal_secret and x_core_internal_key != settings.core_internal_secret:
        raise HTTPException(status_code=401, detail="invalid internal key")
    row = upsert_profile(db, email=body.email, fio=body.fio, role=body.role)
    return {"email": row.email, "fio": row.fio, "role": row.role}
