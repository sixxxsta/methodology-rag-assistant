from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Project, ProjectEnrollment, ProjectRole
from ..services import ensure_workspace, log_action


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
    ws = ensure_workspace(db)
    project = (
        db.query(Project)
        .filter(
            Project.workspace_id == ws.id,
            Project.id == project_id,
            Project.catalog_visible.is_(True),
        )
        .one()
    )

    team_size = project.team_size or 4
    active = active_enrollment_count(db, project.id)
    if active >= team_size:
        raise ValueError("project team is full")

    role: ProjectRole | None = None
    if role_id is not None:
        role = (
            db.query(ProjectRole)
            .filter(ProjectRole.project_id == project.id, ProjectRole.id == role_id)
            .one()
        )
        role_taken = (
            db.query(ProjectEnrollment)
            .filter(
                ProjectEnrollment.role_id == role.id,
                ProjectEnrollment.status == "active",
            )
            .count()
        )
        if role_taken >= role.slots:
            raise ValueError("role has no free slots")

    existing = get_student_enrollment(db, project.id, student_email)
    if existing:
        if existing.status == "active":
            raise ValueError("already enrolled in this project")
        existing.status = "active"
        existing.role_id = role.id if role else None
        existing.student_user_id = student_user_id
        existing.updated_at = datetime.now(timezone.utc)
        enrollment = existing
    else:
        enrollment = ProjectEnrollment(
            project_id=project.id,
            role_id=role.id if role else None,
            student_email=student_email,
            student_user_id=student_user_id,
            status="active",
        )
        db.add(enrollment)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=student_email,
        action="projects.enroll",
        entity_id=str(project.id),
        details=f"role_id={role.id if role else None}",
    )
    db.commit()
    db.refresh(enrollment)
    return _enrollment_dict(enrollment, role)


def withdraw_enrollment(db: Session, project_id: int, *, student_email: str) -> dict:
    ws = ensure_workspace(db)
    enrollment = get_student_enrollment(db, project_id, student_email)
    if not enrollment or enrollment.status != "active":
        raise ValueError("not enrolled in this project")

    project = (
        db.query(Project)
        .filter(Project.workspace_id == ws.id, Project.id == project_id)
        .one()
    )

    enrollment.status = "withdrawn"
    enrollment.updated_at = datetime.now(timezone.utc)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=student_email,
        action="projects.withdraw",
        entity_id=str(project.id),
    )
    db.commit()
    return {"status": "withdrawn", "project_id": project.id}


def list_my_enrollments(db: Session, *, student_email: str) -> list[dict]:
    ws = ensure_workspace(db)
    rows = (
        db.query(ProjectEnrollment, Project, ProjectRole)
        .join(Project, ProjectEnrollment.project_id == Project.id)
        .outerjoin(ProjectRole, ProjectEnrollment.role_id == ProjectRole.id)
        .filter(
            Project.workspace_id == ws.id,
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
