from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent
from .service import (
    approve_shortlist,
    discover_employers,
    enrich_batch,
    enrich_company,
    get_company,
    get_top,
    list_companies,
    reject_company,
    update_company,
    verify_company,
)
from .scoring import get_scoring_weights_public, update_scoring_weights
from .service import _rescore_workspace
from ..services import ensure_workspace, log_action

router = APIRouter(prefix="/companies", tags=["companies"])


class DiscoverIn(BaseModel):
    query: str | None = None
    max_pages: int = Field(default=3, ge=1, le=10)


class CompanyUpdateIn(BaseModel):
    name: str | None = None
    industry: str | None = None
    region: str | None = None
    website: str | None = None
    description: str | None = None
    tech_stack: str | None = None
    employee_count: int | None = None
    size_category: str | None = None
    has_education_program: bool | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_role: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class RejectIn(BaseModel):
    reason: str = ""


class EnrichBatchIn(BaseModel):
    limit: int = Field(default=10, ge=1, le=30)


class ScoringWeightsIn(BaseModel):
    competency: int | None = None
    size: int | None = None
    education: int | None = None
    website: int | None = None
    region: int | None = None


@router.get("/scoring/weights")
def scoring_weights_get(
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"weights": get_scoring_weights_public()}


@router.patch("/scoring/weights")
def scoring_weights_patch(
    body: ScoringWeightsIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        weights = update_scoring_weights(body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ws = ensure_workspace(db)
    count = _rescore_workspace(db, ws.id)
    log_action(db, workspace_id=ws.id, actor_email=user["email"], action="companies.scoring_weights")
    return {"weights": weights, "rescored": count}


@router.get("")
def companies_list(
    limit: int = Query(default=100, le=500),
    status: str | None = None,
    shortlist_only: bool = False,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"companies": list_companies(db, limit=limit, status=status, shortlist_only=shortlist_only)}


@router.get("/top/{n}")
def companies_top(
    n: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    if n not in (10, 20, 100):
        n = min(max(n, 1), 100)
    return get_top(db, n)


@router.get("/{company_id}")
def company_detail(
    company_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    try:
        return get_company(db, company_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/discover")
def discover(
    body: DiscoverIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return discover_employers(
            db,
            actor_email=user["email"],
            query=body.query,
            max_pages=body.max_pages,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/discover/async")
def discover_async(
    body: DiscoverIn,
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    from ..tasks import discover_companies

    task = discover_companies.delay(
        user["email"],
        body.query,
        body.max_pages,
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/discover/jobs/{task_id}")
def discover_job_status(
    task_id: str,
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    from celery.result import AsyncResult

    from ..celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)
    payload: dict = {"task_id": task_id, "status": result.status}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    return payload


@router.post("/rescore")
def rescore(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    ws = ensure_workspace(db)
    count = _rescore_workspace(db, ws.id)
    log_action(db, workspace_id=ws.id, actor_email=user["email"], action="companies.rescore")
    return {"rescored": count}


@router.post("/enrich-batch")
def enrich_many(
    body: EnrichBatchIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    return enrich_batch(db, actor_email=user["email"], limit=body.limit)


@router.patch("/{company_id}")
def patch_company(
    company_id: int,
    body: CompanyUpdateIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return update_company(db, company_id, **body.model_dump(exclude_unset=True))
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{company_id}/verify")
def verify(
    company_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return verify_company(db, company_id, actor_email=user["email"])
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{company_id}/enrich")
def enrich_one(
    company_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return enrich_company(db, company_id, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/{company_id}/reject")
def reject(
    company_id: int,
    body: RejectIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return reject_company(db, company_id, actor_email=user["email"], reason=body.reason)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class BulkShortlistIn(BaseModel):
    limit: int = Field(default=3, ge=1, le=20)


@router.post("/shortlist/fill")
def shortlist_fill(
    body: BulkShortlistIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        from .service import bulk_add_shortlist

        return bulk_add_shortlist(db, actor_email=user["email"], limit=body.limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/shortlist/approve")
def shortlist_approve(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return approve_shortlist(db, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
