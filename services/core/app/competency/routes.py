from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_internal
from .service import build_matrix, collect_from_hh, get_stats, seed_program_competencies
from ..services import ensure_workspace, log_action

router = APIRouter(prefix="/competencies", tags=["competencies"])


class CollectIn(BaseModel):
    query: str = Field(min_length=2, max_length=200)
    area_id: str | None = None
    max_pages: int = Field(default=2, ge=1, le=5)


@router.get("/matrix")
def matrix(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    return build_matrix(db)


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    return get_stats(db)


@router.post("/collect")
def collect(
    body: CollectIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    try:
        return collect_from_hh(
            db,
            actor_email=user["email"],
            query=body.query.strip(),
            area_id=body.area_id,
            max_pages=body.max_pages,
        )
    except Exception as exc:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("collect failed")
        raise HTTPException(status_code=502, detail=f"HH collect failed: {exc}") from exc


@router.post("/program/seed")
def program_seed(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_internal)] = None,
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="admin required")
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
