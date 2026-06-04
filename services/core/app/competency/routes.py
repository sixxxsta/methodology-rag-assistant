from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent
from .providers import list_providers
from .service import (
    build_matrix,
    collect_vacancies,
    export_matrix_csv,
    get_stats,
    matrix_chart,
    seed_program_competencies,
)
from ..services import ensure_workspace, log_action

router = APIRouter(prefix="/competencies", tags=["competencies"])


class CollectIn(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    area_id: str | None = None
    max_pages: int = Field(default=2, ge=1, le=5)
    provider: Literal["hh", "superjob"] = "hh"


@router.get("/matrix")
def matrix(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return build_matrix(db)


@router.get("/matrix/chart")
def matrix_chart_route(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return matrix_chart(db)


@router.get("/matrix/export")
def matrix_export(
    format: str = Query(default="csv"),
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="only csv format supported")
    csv_data = export_matrix_csv(db)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="competency_matrix.csv"'},
    )


@router.get("/providers")
def providers(
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"providers": list_providers()}


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return get_stats(db)


@router.post("/collect")
def collect(
    body: CollectIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return collect_vacancies(
            db,
            actor_email=user["email"],
            query=body.query.strip(),
            area_id=body.area_id,
            max_pages=body.max_pages,
            provider=body.provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("collect failed")
        raise HTTPException(status_code=502, detail=f"vacancy collect failed: {exc}") from exc


@router.post("/program/seed")
def program_seed(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    ws = ensure_workspace(db)
    count = seed_program_competencies(db, ws.id)
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=user["email"],
        action="competency.program_seed",
        details=f"count={count}",
    )
    db.commit()
    return {"seeded": count}
