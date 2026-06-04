from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Project, ProjectEnrollment, ProjectRole
from ..services import log_action
from .catalog import catalog_visible_filter


def _enrollment_dict(enrollment: ProjectEnrollment, role: ProjectRole | None = None) -> dict:
    return {
        "id": enrollment.id,
        "project_id": enrollment.project_id,
        "role_id": enrollment.role_id,
        "role_title": role.title if role else None,
        "student_email": enrollment.student_email,
        "status": enrollment.status,
        "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
    }


def active_enrollment_count(db: Session, project_id: int) -> int:
    return (
        db.query(ProjectEnrollment)
        .filter(ProjectEnrollment.project_id == project_id, ProjectEnrollment.status == "active")
        .count()
    )


def get_student_enrollment(
    db: Session, project_id: int, student_email: str
) -> ProjectEnrollment | None:
    return (
        db.query(ProjectEnrollment)
        .filter(
            ProjectEnrollment.project_id == project_id,
            ProjectEnrollment.student_email == student_email,
        )
        .one_or_none()
    )


def enroll_student(
    db: Session,
    project_id: int,
    *,
    student_email: str,
    student_user_id: str | None,
    role_id: int | None = None,
) -> dict:
    raise ValueError(
        "запись только через команду: создайте команду, лидер выбирает проект в каталоге"
    )


def withdraw_enrollment(db: Session, project_id: int, *, student_email: str) -> dict:
    from .team_claims import get_active_claim_for_team, withdraw_team_claim
    from ..teams.service import _active_team_for_student, _norm

    email = _norm(student_email)
    team = _active_team_for_student(db, email)
    if team and _norm(team.leader_email) == email:
        claim = get_active_claim_for_team(db, team.id)
        if claim and claim.project_id == project_id:
            return withdraw_team_claim(db, project_id, leader_email=email)
    raise ValueError("only the team leader can cancel the team's project claim")


def list_my_enrollments(db: Session, *, student_email: str) -> list[dict]:
    from ..teams.service import _active_team_for_student, _norm
    from .team_claims import get_active_claim_for_team

    email = _norm(student_email)
    team = _active_team_for_student(db, email)
    if team:
        claim = get_active_claim_for_team(db, team.id)
        if claim:
            project = db.query(Project).filter(Project.id == claim.project_id).one_or_none()
            if project:
                return [
                    {
                        "id": claim.id,
                        "project_id": project.id,
                        "project_title": project.title,
                        "role_id": None,
                        "role_title": None,
                        "student_email": email,
                        "status": "active",
                        "via_team": True,
                        "team_id": team.id,
                        "is_leader": _norm(team.leader_email) == email,
                    }
                ]

    rows = (
        db.query(ProjectEnrollment, Project, ProjectRole)
        .join(Project, ProjectEnrollment.project_id == Project.id)
        .outerjoin(ProjectRole, ProjectEnrollment.role_id == ProjectRole.id)
        .filter(
            ProjectEnrollment.student_email == student_email,
            ProjectEnrollment.status == "active",
        )
        .order_by(ProjectEnrollment.created_at.desc())
        .all()
    )
    return [
        {
            **_enrollment_dict(enrollment, role),
            "project_title": project.title,
            "company_id": project.company_id,
        }
        for enrollment, project, role in rows
    ]
