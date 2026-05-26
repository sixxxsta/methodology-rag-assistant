from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_internal
from .service import (
    approve_project,
    complete_projects_phase,
    dashboard,
    generate_project,
    get_project,
    list_catalog,
    publish_to_catalog,
    update_project,
)

router = APIRouter(prefix="/projects", tags=["projects"])


class GenerateIn(BaseModel):
    agreement_id: int | None = None


class UpdateIn(BaseModel):
    title: str | None = None
    spec_markdown: str | None = None
    team_size: int | None = None
    duration_weeks: int | None = None
    competencies: str | None = None


@router.get("/dashboard")
def projects_dashboard(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    return dashboard(db)


@router.get("/catalog")
def catalog(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    return {"items": list_catalog(db)}


@router.get("/{project_id}")
def project_detail(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    try:
        return get_project(db, project_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/companies/{company_id}/generate")
def generate(
    company_id: int,
    body: GenerateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return generate_project(
            db,
            company_id,
            actor_email=user["email"],
            agreement_id=body.agreement_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{project_id}")
def patch_project(
    project_id: int,
    body: UpdateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return update_project(
            db,
            project_id,
            actor_email=user["email"],
            title=body.title,
            spec_markdown=body.spec_markdown,
            team_size=body.team_size,
            duration_weeks=body.duration_weeks,
            competencies=body.competencies,
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/approve")
def approve(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return approve_project(db, project_id, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/publish")
def publish(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return publish_to_catalog(db, project_id, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/phase/complete")
def phase_complete(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return complete_projects_phase(db, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
