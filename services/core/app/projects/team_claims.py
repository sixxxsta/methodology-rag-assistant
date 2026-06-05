from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Project, ProjectEnrollment, ProjectTeamClaim, StudentTeam, StudentTeamMember
from ..profiles.service import display_name
from ..services import log_action
from ..teams.service import TEAM_STATUS_ACTIVE, _active_team_for_student, _norm
from .catalog import catalog_visible_filter
from .interviews import interview_context, interview_passed
from .limits import MIN_TEAM_MEMBERS_TO_CLAIM, clamp_team_size


CLAIM_ACTIVE = "active"
CLAIM_WITHDRAWN = "withdrawn"


def active_team_claims_count(db: Session, project_id: int) -> int:
    return (
        db.query(ProjectTeamClaim)
        .filter(
            ProjectTeamClaim.project_id == project_id,
            ProjectTeamClaim.status == CLAIM_ACTIVE,
        )
        .count()
    )


def get_active_claim_for_team(db: Session, team_id: int) -> ProjectTeamClaim | None:
    return (
        db.query(ProjectTeamClaim)
        .filter(
            ProjectTeamClaim.team_id == team_id,
            ProjectTeamClaim.status == CLAIM_ACTIVE,
        )
        .order_by(ProjectTeamClaim.id.desc())
        .first()
    )


def team_claim_in_cycle(
    db: Session, team_id: int, cycle_id: int, *, exclude_project_id: int | None = None
) -> ProjectTeamClaim | None:
    """Any claim (active or withdrawn) by this team on a project in the partnership cycle (semester)."""
    q = (
        db.query(ProjectTeamClaim)
        .join(Project, ProjectTeamClaim.project_id == Project.id)
        .filter(
            ProjectTeamClaim.team_id == team_id,
            Project.cycle_id == cycle_id,
            ProjectTeamClaim.status.in_((CLAIM_ACTIVE, CLAIM_WITHDRAWN)),
        )
    )
    if exclude_project_id is not None:
        q = q.filter(ProjectTeamClaim.project_id != exclude_project_id)
    return q.order_by(ProjectTeamClaim.id.desc()).first()


def _claim_dict(claim: ProjectTeamClaim, project: Project | None = None) -> dict:
    return {
        "id": claim.id,
        "project_id": claim.project_id,
        "project_title": project.title if project else None,
        "team_id": claim.team_id,
        "leader_email": claim.leader_email,
        "status": claim.status,
        "created_at": claim.created_at.isoformat() if claim.created_at else None,
    }


def list_project_claims(db: Session, project_id: int) -> list[dict]:
    rows = (
        db.query(ProjectTeamClaim, StudentTeam)
        .join(StudentTeam, ProjectTeamClaim.team_id == StudentTeam.id)
        .filter(
            ProjectTeamClaim.project_id == project_id,
            ProjectTeamClaim.status == CLAIM_ACTIVE,
        )
        .order_by(ProjectTeamClaim.created_at.asc())
        .all()
    )
    out: list[dict] = []
    for claim, team in rows:
        member_count = (
            db.query(StudentTeamMember)
            .filter(StudentTeamMember.team_id == team.id)
            .count()
        )
        out.append(
            {
                "claim_id": claim.id,
                "team_id": team.id,
                "team_name": team.name or f"Команда #{team.id}",
                "leader_email": claim.leader_email,
                "leader_fio": display_name(db, claim.leader_email),
                "member_count": member_count,
                "claimed_at": claim.created_at.isoformat() if claim.created_at else None,
            }
        )
    return out


def catalog_teams_meta(db: Session, project: Project) -> dict:
    max_teams = project.max_teams or 1
    claimed = active_team_claims_count(db, project.id)
    member_size = clamp_team_size(project.team_size)
    return {
        "max_teams": max_teams,
        "teams_claimed": claimed,
        "teams_left": max(0, max_teams - claimed),
        "team_member_size": member_size,
        "team_size": member_size,
    }


def viewer_team_context(
    db: Session, project_id: int, *, viewer_email: str | None
) -> dict:
    empty_interview = {
        "interview_required": False,
        "interview_status": None,
        "interview_questions": [],
        "interview_feedback": None,
        "can_start_interview": False,
        "can_submit_interview": False,
        "interview_passed": True,
    }
    if not viewer_email:
        return {
            "my_team": None,
            "my_team_claim": None,
            "can_claim_as_leader": False,
            "min_team_members_to_claim": MIN_TEAM_MEMBERS_TO_CLAIM,
            "team_member_count": 0,
            "team_members_short": MIN_TEAM_MEMBERS_TO_CLAIM,
            "semester_claim_blocked": False,
            "semester_claim_block_reason": None,
            **empty_interview,
        }

    email = _norm(viewer_email)
    team = _active_team_for_student(db, email)
    if not team:
        return {
            "my_team": None,
            "my_team_claim": None,
            "can_claim_as_leader": False,
            "min_team_members_to_claim": MIN_TEAM_MEMBERS_TO_CLAIM,
            "team_member_count": 0,
            "team_members_short": MIN_TEAM_MEMBERS_TO_CLAIM,
            "semester_claim_blocked": False,
            "semester_claim_block_reason": None,
            **empty_interview,
        }

    from ..teams.service import _team_dict

    claim = get_active_claim_for_team(db, team.id)
    my_claim = None
    semester_blocked = False
    semester_block_reason: str | None = None
    if claim:
        proj = db.query(Project).filter(Project.id == claim.project_id).one_or_none()
        my_claim = _claim_dict(claim, proj)

    is_leader = _norm(team.leader_email) == email
    member_count = (
        db.query(StudentTeamMember)
        .filter(StudentTeamMember.team_id == team.id)
        .count()
    )
    min_required = MIN_TEAM_MEMBERS_TO_CLAIM
    project = db.query(Project).filter(Project.id == project_id).one_or_none()
    teams_left = catalog_teams_meta(db, project)["teams_left"] if project else 0

    if project:
        prior = team_claim_in_cycle(db, team.id, project.cycle_id, exclude_project_id=project_id)
        if prior:
            semester_blocked = True
            prior_proj = db.query(Project).filter(Project.id == prior.project_id).one_or_none()
            title = prior_proj.title if prior_proj else f"#{prior.project_id}"
            semester_block_reason = (
                f"команда уже выбирала проект в этом семестре: «{title}». "
                "Раз в семестр доступен только один проект."
            )

    interview_ok = True
    if project and getattr(project, "interview_required", False):
        interview_ok = interview_passed(db, project.id, team.id)

    can_claim = bool(
        is_leader
        and claim is None
        and not semester_blocked
        and teams_left > 0
        and project is not None
        and member_count >= min_required
        and interview_ok
    )

    iv_ctx = interview_context(
        db,
        project,
        viewer_email=email,
        is_leader=is_leader,
        team_id=team.id,
    ) if project else empty_interview

    return {
        "my_team": _team_dict(db, team, viewer_email=email),
        "my_team_claim": my_claim,
        "can_claim_as_leader": can_claim,
        "min_team_members_to_claim": min_required,
        "team_member_count": member_count,
        "team_members_short": max(0, min_required - member_count),
        "semester_claim_blocked": semester_blocked,
        "semester_claim_block_reason": semester_block_reason,
        **iv_ctx,
    }


def claim_project_for_team(
    db: Session,
    project_id: int,
    *,
    leader_email: str,
    leader_user_id: str | None = None,
) -> dict:
    email = _norm(leader_email)
    team = _active_team_for_student(db, email)
    if not team or _norm(team.leader_email) != email:
        raise ValueError("only the team leader can select a project")

    existing_claim = get_active_claim_for_team(db, team.id)
    if existing_claim:
        if existing_claim.project_id == project_id:
            raise ValueError("team already claimed this project")
        raise ValueError("team already has another project; withdraw it first")

    project = (
        db.query(Project)
        .filter(Project.id == project_id, *catalog_visible_filter())
        .one()
    )

    prior = team_claim_in_cycle(db, team.id, project.cycle_id, exclude_project_id=project_id)
    if prior:
        prior_proj = db.query(Project).filter(Project.id == prior.project_id).one_or_none()
        title = prior_proj.title if prior_proj else f"#{prior.project_id}"
        raise ValueError(
            f"команда уже выбирала проект в этом семестре: «{title}». "
            "Раз в семестр доступен только один проект"
        )

    max_teams = project.max_teams or 1
    if active_team_claims_count(db, project.id) >= max_teams:
        raise ValueError("no team slots left on this project")

    members = (
        db.query(StudentTeamMember)
        .filter(StudentTeamMember.team_id == team.id)
        .all()
    )
    member_count = len(members)
    team_cap = clamp_team_size(project.team_size)
    if member_count > team_cap:
        raise ValueError(f"team has {member_count} members; project allows {team_cap}")
    if member_count < MIN_TEAM_MEMBERS_TO_CLAIM:
        raise ValueError(
            f"в команде {member_count} чел.; для выбора проекта нужно минимум {MIN_TEAM_MEMBERS_TO_CLAIM}"
        )

    if getattr(project, "interview_required", False) and not interview_passed(db, project.id, team.id):
        raise ValueError("сначала пройдите собеседование по этому проекту")

    claim = ProjectTeamClaim(
        project_id=project.id,
        team_id=team.id,
        leader_email=email,
        status=CLAIM_ACTIVE,
    )
    db.add(claim)
    db.flush()

    now = datetime.now(timezone.utc)
    for m in members:
        row = (
            db.query(ProjectEnrollment)
            .filter(
                ProjectEnrollment.project_id == project.id,
                ProjectEnrollment.student_email == m.student_email,
            )
            .one_or_none()
        )
        if row:
            if row.status == "active":
                continue
            row.status = "active"
            row.team_id = team.id
            row.student_user_id = m.student_user_id
            row.updated_at = now
        else:
            db.add(
                ProjectEnrollment(
                    project_id=project.id,
                    student_email=m.student_email,
                    student_user_id=m.student_user_id,
                    team_id=team.id,
                    status="active",
                )
            )

    log_action(
        db,
        workspace_id=project.workspace_id,
        actor_email=email,
        action="projects.team_claim",
        entity_id=str(project.id),
        details=f"team_id={team.id}",
    )
    db.commit()
    db.refresh(claim)
    return _claim_dict(claim, project)


def withdraw_team_claim(
    db: Session,
    project_id: int,
    *,
    leader_email: str,
) -> dict:
    email = _norm(leader_email)
    team = _active_team_for_student(db, email)
    if not team or _norm(team.leader_email) != email:
        raise ValueError("only the team leader can withdraw")

    claim = (
        db.query(ProjectTeamClaim)
        .filter(
            ProjectTeamClaim.project_id == project_id,
            ProjectTeamClaim.team_id == team.id,
            ProjectTeamClaim.status == CLAIM_ACTIVE,
        )
        .one_or_none()
    )
    if not claim:
        raise ValueError("team has no active claim on this project")

    claim.status = CLAIM_WITHDRAWN
    now = datetime.now(timezone.utc)
    member_emails = [
        m.student_email
        for m in db.query(StudentTeamMember)
        .filter(StudentTeamMember.team_id == team.id)
        .all()
    ]
    (
        db.query(ProjectEnrollment)
        .filter(
            ProjectEnrollment.project_id == project_id,
            ProjectEnrollment.student_email.in_(member_emails),
            ProjectEnrollment.status == "active",
        )
        .update({ProjectEnrollment.status: "withdrawn", ProjectEnrollment.updated_at: now})
    )

    project = db.query(Project).filter(Project.id == project_id).one()
    log_action(
        db,
        workspace_id=project.workspace_id,
        actor_email=email,
        action="projects.team_claim.withdraw",
        entity_id=str(project_id),
    )
    db.commit()
    return {"status": "withdrawn", "project_id": project_id, "team_id": team.id}
