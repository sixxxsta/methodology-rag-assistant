from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent, require_internal, require_student
from .service import (
    approve_project,
    complete_projects_phase,
    dashboard,
    generate_project,
    get_catalog_project,
    get_project,
    list_catalog,
    publish_to_catalog,
    resync_project_roles,
    update_project,
)
from .matching import get_student_profile, recommend_projects, upsert_student_profile
from .enrollment import enroll_student, list_my_enrollments, withdraw_enrollment
from .roles import list_project_roles

router = APIRouter(prefix="/projects", tags=["projects"])


class GenerateIn(BaseModel):
    agreement_id: int | None = None


class UpdateIn(BaseModel):
    title: str | None = None
    spec_markdown: str | None = None
    team_size: int | None = None
    duration_weeks: int | None = None
    competencies: str | None = None


class EnrollIn(BaseModel):
    role_id: int | None = None


class StudentProfileIn(BaseModel):
    skills: str
    notes: str | None = None


@router.get("/recommendations")
def project_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    return {"items": recommend_projects(db, student_email=user["email"], limit=limit)}


@router.get("/profile")
def student_profile_get(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    profile = get_student_profile(db, user["email"])
    return {"profile": profile}


@router.put("/profile")
def student_profile_put(
    body: StudentProfileIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    profile = upsert_student_profile(
        db,
        student_email=user["email"],
        skills=body.skills,
        notes=body.notes,
    )
    return {"profile": profile}


@router.get("/dashboard")
def projects_dashboard(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return dashboard(db)


@router.get("/my-enrollments")
def my_enrollments(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    return {"items": list_my_enrollments(db, student_email=user["email"])}


@router.get("/catalog")
def catalog(
    competencies: str | None = Query(default=None, description="Comma-separated skills filter"),
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    filters = [part.strip() for part in (competencies or "").split(",") if part.strip()]
    return {"items": list_catalog(db, competencies=filters or None)}


@router.get("/catalog/{project_id}")
def catalog_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    try:
        return get_catalog_project(db, project_id, viewer_email=user["email"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/catalog/{project_id}/enroll")
def catalog_enroll(
    project_id: int,
    body: EnrollIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        return enroll_student(
            db,
            project_id,
            student_email=user["email"],
            student_user_id=user.get("user_id"),
            role_id=body.role_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/catalog/{project_id}/enroll")
def catalog_withdraw(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        return withdraw_enrollment(db, project_id, student_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{project_id}/roles")
def project_roles(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    try:
        return {"roles": list_project_roles(db, project_id)}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{project_id}/roles/sync")
def project_roles_sync(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return resync_project_roles(db, project_id, actor_email=user["email"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{project_id}")
def project_detail(
    project_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    try:
        data = get_project(db, project_id)
        data["roles"] = list_project_roles(db, project_id)
        return data
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/companies/{company_id}/generate")
def generate(
    company_id: int,
    body: GenerateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
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
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
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
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
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
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return publish_to_catalog(db, project_id, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/phase/complete")
def phase_complete(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return complete_projects_phase(db, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
