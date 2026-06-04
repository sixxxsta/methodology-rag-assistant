from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Company, Project, StudentProfile
from ..services import ensure_workspace
from .enrollment import active_enrollment_count
from .service import _catalog_meta, _project_dict


def _parse_skills(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.replace(";", ",").split(",") if part.strip()}


def upsert_student_profile(
    db: Session,
    *,
    student_email: str,
    skills: str,
    notes: str | None = None,
) -> dict:
    email = student_email.strip().lower()
    row = db.query(StudentProfile).filter(StudentProfile.student_email == email).one_or_none()
    if row:
        row.skills = skills
        row.notes = notes
    else:
        row = StudentProfile(student_email=email, skills=skills, notes=notes)
        db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "student_email": row.student_email,
        "skills": row.skills,
        "notes": row.notes,
    }


def get_student_profile(db: Session, student_email: str) -> dict | None:
    row = (
        db.query(StudentProfile)
        .filter(StudentProfile.student_email == student_email.strip().lower())
        .one_or_none()
    )
    if not row:
        return None
    return {"student_email": row.student_email, "skills": row.skills, "notes": row.notes}


def recommend_projects(db: Session, *, student_email: str, limit: int = 10) -> list[dict]:
    ws = ensure_workspace(db)
    profile = get_student_profile(db, student_email)
    student_skills = _parse_skills(profile["skills"] if profile else None)

    rows = (
        db.query(Project, Company)
        .outerjoin(Company, Project.company_id == Company.id)
        .filter(Project.workspace_id == ws.id, Project.catalog_visible.is_(True))
        .all()
    )

    scored: list[tuple[int, dict]] = []
    for proj, co in rows:
        enrolled = active_enrollment_count(db, proj.id)
        team_size = proj.team_size or 4
        if enrolled >= team_size:
            continue

        project_skills = _parse_skills(proj.competencies)
        if not project_skills and proj.spec_markdown:
            from ..competency.skills import extract_skills

            project_skills = set(s.lower() for s in extract_skills(proj.spec_markdown))

        overlap = len(student_skills & project_skills) if student_skills and project_skills else 0
        skill_score = 0
        if student_skills and project_skills:
            skill_score = int(overlap / max(len(project_skills), 1) * 100)
        elif project_skills:
            skill_score = 10

        seats_left = max(0, team_size - enrolled)
        seat_bonus = min(15, seats_left * 3)
        score = min(100, skill_score + seat_bonus)

        item = _project_dict(proj, co.name if co else None)
        item.update(_catalog_meta(db, proj))
        item["match_score"] = score
        item["skill_overlap"] = overlap
        item["matched_skills"] = sorted(student_skills & project_skills)
        scored.append((score, item))

    scored.sort(key=lambda x: (-x[0], x[1].get("title", "")))
    return [item for _, item in scored[: max(1, min(limit, 50))]]
