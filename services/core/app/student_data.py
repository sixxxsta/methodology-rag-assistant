from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    ProjectEnrollment,
    ProjectTeamClaim,
    StudentProfile,
    StudentTeam,
    StudentTeamMember,
)


def purge_student_data(db: Session, *, student_email: str) -> dict:
    email = student_email.strip().lower()
    team_ids = [
        tid
        for (tid,) in db.query(StudentTeamMember.team_id)
        .filter(StudentTeamMember.student_email == email)
        .all()
    ]
    claims_removed = 0
    if team_ids:
        claims_removed = (
            db.query(ProjectTeamClaim)
            .filter(ProjectTeamClaim.team_id.in_(team_ids))
            .delete(synchronize_session=False)
        )
        db.query(StudentTeamMember).filter(StudentTeamMember.team_id.in_(team_ids)).delete(
            synchronize_session=False
        )
        db.query(StudentTeam).filter(StudentTeam.id.in_(team_ids)).delete(synchronize_session=False)

    enrollments = (
        db.query(ProjectEnrollment)
        .filter(ProjectEnrollment.student_email == email)
        .delete(synchronize_session=False)
    )
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.student_email == email)
        .delete(synchronize_session=False)
    )
    db.commit()
    return {
        "student_email": email,
        "enrollments_removed": enrollments,
        "profile_removed": profile,
        "teams_removed": len(team_ids),
        "claims_removed": claims_removed,
    }
