from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_curator, require_edagent
from .service import create_cycle, list_cycles, reopen_phase, set_active_cycle

router = APIRouter(prefix="/cycles", tags=["cycles"])


class CreateCycleIn(BaseModel):
    name: str | None = Field(default=None, max_length=255)


@router.get("")
def cycles_list(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_edagent)] = None,
):
    return {"cycles": list_cycles(db)}


@router.post("")
def cycles_create(
    body: CreateCycleIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        cycle = create_cycle(db, name=body.name, actor_email=user["email"], activate=True)
        return {"cycle": cycle}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{cycle_id}/activate")
def cycles_activate(
    cycle_id: int,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return {"cycle": set_active_cycle(db, cycle_id, actor_email=user["email"])}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{cycle_id}/phases/{phase_key}/reopen")
def cycles_reopen_phase(
    cycle_id: int,
    phase_key: str,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_curator)] = None,
):
    try:
        return reopen_phase(db, cycle_id, phase_key, actor_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
