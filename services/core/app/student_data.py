from __future__ import annotations

from sqlalchemy.orm import Session

from .models import ProjectEnrollment, StudentProfile


def purge_student_data(db: Session, *, student_email: str) -> dict:
    email = student_email.strip().lower()
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
    return {"student_email": email, "enrollments_removed": enrollments, "profile_removed": profile}
