from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_student
from .service import create_team, get_my_team, join_team, leave_team, transfer_leadership

router = APIRouter(prefix="/teams", tags=["teams"])


class CreateTeamIn(BaseModel):
    name: str | None = Field(default=None, max_length=255)


class JoinTeamIn(BaseModel):
    invite_code: str = Field(min_length=4, max_length=32)


class TransferLeadershipIn(BaseModel):
    new_leader_email: str = Field(min_length=3, max_length=255)


@router.get("/me")
def teams_me(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    team = get_my_team(db, student_email=user["email"])
    return {"team": team}


@router.post("")
def teams_create(
    body: CreateTeamIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        team = create_team(
            db,
            leader_email=user["email"],
            leader_user_id=user.get("user_id"),
            name=body.name,
        )
        return {"team": team}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/join")
def teams_join(
    body: JoinTeamIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        team = join_team(
            db,
            student_email=user["email"],
            student_user_id=user.get("user_id"),
            invite_code=body.invite_code,
        )
        return {"team": team}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/leave")
def teams_leave(
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        return leave_team(db, student_email=user["email"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/transfer-leadership")
def teams_transfer(
    body: TransferLeadershipIn,
    db: Session = Depends(get_db),
    user: Annotated[dict[str, str], Depends(require_student)] = None,
):
    try:
        team = transfer_leadership(
            db,
            leader_email=user["email"],
            new_leader_email=body.new_leader_email,
        )
        return {"team": team}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
