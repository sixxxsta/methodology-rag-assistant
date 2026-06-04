from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import StudentTeam, StudentTeamMember
from ..projects.limits import MAX_TEAM_MEMBERS
from ..services import log_action

TEAM_STATUS_ACTIVE = "active"
TEAM_STATUS_CLOSED = "closed"


def _norm(email: str) -> str:
    return email.strip().lower()


def _new_invite_code() -> str:
    return secrets.token_urlsafe(6).upper().replace("-", "")[:10]


def _member_row(db: Session, team_id: int, email: str) -> StudentTeamMember | None:
    return (
        db.query(StudentTeamMember)
        .filter(
            StudentTeamMember.team_id == team_id,
            StudentTeamMember.student_email == _norm(email),
        )
        .one_or_none()
    )


def _active_team_for_student(db: Session, email: str) -> StudentTeam | None:
    email = _norm(email)
    row = (
        db.query(StudentTeam)
        .join(StudentTeamMember, StudentTeamMember.team_id == StudentTeam.id)
        .filter(
            StudentTeamMember.student_email == email,
            StudentTeam.status == TEAM_STATUS_ACTIVE,
        )
        .order_by(StudentTeam.id.desc())
        .first()
    )
    return row


def _team_dict(db: Session, team: StudentTeam, *, viewer_email: str) -> dict:
    members = (
        db.query(StudentTeamMember)
        .filter(StudentTeamMember.team_id == team.id)
        .order_by(StudentTeamMember.is_leader.desc(), StudentTeamMember.joined_at)
        .all()
    )
    email = _norm(viewer_email)
    return {
        "id": team.id,
        "name": team.name,
        "leader_email": team.leader_email,
        "invite_code": team.invite_code,
        "max_members": team.max_members,
        "member_count": len(members),
        "status": team.status,
        "is_leader": email == _norm(team.leader_email),
        "members": [
            {
                "student_email": m.student_email,
                "is_leader": m.is_leader,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            for m in members
        ],
    }


def get_my_team(db: Session, *, student_email: str) -> dict | None:
    team = _active_team_for_student(db, student_email)
    if not team:
        return None
    return _team_dict(db, team, viewer_email=student_email)


def create_team(
    db: Session,
    *,
    leader_email: str,
    leader_user_id: str | None = None,
    name: str | None = None,
    max_members: int = MAX_TEAM_MEMBERS,
) -> dict:
    email = _norm(leader_email)
    if _active_team_for_student(db, email):
        raise ValueError("already in a team; leave current team first")

    max_members = MAX_TEAM_MEMBERS

    team = StudentTeam(
        name=(name or "").strip() or f"Команда {email.split('@')[0]}",
        leader_email=email,
        invite_code=_new_invite_code(),
        max_members=max_members,
        status=TEAM_STATUS_ACTIVE,
    )
    db.add(team)
    db.flush()
    db.add(
        StudentTeamMember(
            team_id=team.id,
            student_email=email,
            student_user_id=leader_user_id,
            is_leader=True,
        )
    )
    log_action(
        db,
        workspace_id=None,
        actor_email=email,
        action="teams.create",
        entity_id=str(team.id),
    )
    db.commit()
    db.refresh(team)
    return _team_dict(db, team, viewer_email=email)


def join_team(
    db: Session,
    *,
    student_email: str,
    student_user_id: str | None,
    invite_code: str,
) -> dict:
    email = _norm(student_email)
    if _active_team_for_student(db, email):
        raise ValueError("already in a team")

    code = (invite_code or "").strip().upper()
    team = (
        db.query(StudentTeam)
        .filter(StudentTeam.invite_code == code, StudentTeam.status == TEAM_STATUS_ACTIVE)
        .one_or_none()
    )
    if not team:
        raise ValueError("invalid invite code")

    count = db.query(StudentTeamMember).filter(StudentTeamMember.team_id == team.id).count()
    cap = min(team.max_members, MAX_TEAM_MEMBERS)
    if count >= cap:
        raise ValueError("team is full")

    db.add(
        StudentTeamMember(
            team_id=team.id,
            student_email=email,
            student_user_id=student_user_id,
            is_leader=False,
        )
    )
    log_action(
        db,
        workspace_id=None,
        actor_email=email,
        action="teams.join",
        entity_id=str(team.id),
    )
    db.commit()
    db.refresh(team)
    return _team_dict(db, team, viewer_email=email)


def leave_team(db: Session, *, student_email: str) -> dict:
    email = _norm(student_email)
    team = _active_team_for_student(db, email)
    if not team:
        raise ValueError("not in a team")

    member = _member_row(db, team.id, email)
    if not member:
        raise ValueError("not in a team")

    from ..projects.team_claims import get_active_claim_for_team

    if get_active_claim_for_team(db, team.id):
        raise ValueError("leave or cancel project claim before leaving the team")

    members_count = db.query(StudentTeamMember).filter(StudentTeamMember.team_id == team.id).count()

    if member.is_leader:
        if members_count > 1:
            raise ValueError("transfer leadership to another member before leaving")
        team.status = TEAM_STATUS_CLOSED
        db.query(StudentTeamMember).filter(StudentTeamMember.team_id == team.id).delete()
    else:
        db.delete(member)

    log_action(
        db,
        workspace_id=None,
        actor_email=email,
        action="teams.leave",
        entity_id=str(team.id),
    )
    db.commit()
    return {"status": "left", "team_id": team.id}


def transfer_leadership(
    db: Session,
    *,
    leader_email: str,
    new_leader_email: str,
) -> dict:
    email = _norm(leader_email)
    new_email = _norm(new_leader_email)
    if email == new_email:
        raise ValueError("choose a different member")

    team = _active_team_for_student(db, email)
    if not team or _norm(team.leader_email) != email:
        raise ValueError("only the team leader can transfer leadership")

    new_member = _member_row(db, team.id, new_email)
    if not new_member:
        raise ValueError("new leader must be a team member")

    old_leader = _member_row(db, team.id, email)
    if old_leader:
        old_leader.is_leader = False
    new_member.is_leader = True
    team.leader_email = new_email
    team.updated_at = datetime.now(timezone.utc)

    log_action(
        db,
        workspace_id=None,
        actor_email=email,
        action="teams.transfer_leadership",
        entity_id=str(team.id),
        details=new_email,
    )
    db.commit()
    db.refresh(team)
    return _team_dict(db, team, viewer_email=new_email)
