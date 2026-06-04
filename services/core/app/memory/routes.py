from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent
from .strategy import get_strategy_hints, list_patterns, memory_stats, sync_all_from_outcomes
from .qlora_export import export_training_jsonl

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return memory_stats(db)


@router.get("/strategies")
def strategies(
    category: str | None = None,
    tone: str | None = None,
    outcome: str | None = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"patterns": list_patterns(db, category=category, tone=tone, outcome=outcome, limit=limit)}


@router.get("/hints")
def hints(
    category: str = "letter",
    tone: str | None = "formal",
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    text = get_strategy_hints(db, category=category, tone=tone)
    return {"category": category, "tone": tone, "hints": text}


@router.post("/sync")
def sync(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    return sync_all_from_outcomes(db, actor_email=user["email"])


@router.post("/qlora/export")
def qlora_export(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    return export_training_jsonl(db)
