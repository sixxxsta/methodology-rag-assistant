from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import Project, ProjectEnrollment, ProjectRole


def parse_roles_from_spec(spec: str) -> list[dict]:
    if not spec:
        return []

    section = _extract_roles_section(spec)
    if not section:
        return []

    roles: list[dict] = []
    order = 0
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line or not line[0] in "-*•":
            continue
        line = re.sub(r"^[-*•]\s*", "", line).strip()
        if not line:
            continue

        title = line
        skills: str | None = None
        hours: int | None = None
        slots = 1

        if ":" in line:
            title, rest = line.split(":", 1)
            title = title.strip(" *#")
            skills = rest.strip(" -—")
        elif "—" in line:
            title, rest = line.split("—", 1)
            title = title.strip(" *#")
            skills = rest.strip()
        elif " - " in line:
            title, rest = line.split(" - ", 1)
            title = title.strip(" *#")
            skills = rest.strip()

        title = re.sub(r"^\*\*|\*\*$", "", title).strip()
        if skills:
            hours_match = re.search(r"(\d+)\s*ч\s*/?\s*нед", skills, re.IGNORECASE)
            if hours_match:
                hours = int(hours_match.group(1))
                skills = re.sub(r"\(?\s*\d+\s*ч\s*/?\s*нед\.?\s*\)?", "", skills, flags=re.IGNORECASE).strip(" ,—")

        roles.append(
            {
                "title": title or "Участник команды",
                "skills": skills,
                "hours_per_week": hours,
                "slots": slots,
                "sort_order": order,
            }
        )
        order += 1

    return roles


def _extract_roles_section(spec: str) -> str:
    pattern = re.compile(
        r"^##\s*Роли в команде\s*$([\s\S]*?)(?=^##\s|\Z)",
        re.MULTILINE | re.IGNORECASE,
    )
    match = pattern.search(spec)
    return match.group(1).strip() if match else ""


def _role_dict(role: ProjectRole, enrolled: int = 0) -> dict:
    return {
        "id": role.id,
        "project_id": role.project_id,
        "title": role.title,
        "skills": role.skills,
        "hours_per_week": role.hours_per_week,
        "slots": role.slots,
        "sort_order": role.sort_order,
        "enrolled_count": enrolled,
        "seats_left": max(0, role.slots - enrolled),
    }


def sync_roles_from_spec(db: Session, project: Project) -> list[dict]:
    parsed = parse_roles_from_spec(project.spec_markdown or "")
    if not parsed:
        team = project.team_size or 4
        parsed = [
            {
                "title": "Участник команды",
                "skills": project.competencies,
                "hours_per_week": None,
                "slots": team,
                "sort_order": 0,
            }
        ]

    db.query(ProjectEnrollment).filter(ProjectEnrollment.project_id == project.id).update(
        {ProjectEnrollment.role_id: None}
    )
    db.query(ProjectRole).filter(ProjectRole.project_id == project.id).delete()
    created: list[ProjectRole] = []
    for item in parsed:
        role = ProjectRole(
            project_id=project.id,
            title=item["title"],
            skills=item.get("skills"),
            hours_per_week=item.get("hours_per_week"),
            slots=max(1, int(item.get("slots") or 1)),
            sort_order=int(item.get("sort_order") or 0),
        )
        db.add(role)
        created.append(role)
    db.flush()
    return [_role_dict(r) for r in created]


def list_project_roles(db: Session, project_id: int) -> list[dict]:
    from ..models import ProjectEnrollment

    roles = (
        db.query(ProjectRole)
        .filter(ProjectRole.project_id == project_id)
        .order_by(ProjectRole.sort_order, ProjectRole.id)
        .all()
    )
    out: list[dict] = []
    for role in roles:
        enrolled = (
            db.query(ProjectEnrollment)
            .filter(
                ProjectEnrollment.role_id == role.id,
                ProjectEnrollment.status == "active",
            )
            .count()
        )
        out.append(_role_dict(role, enrolled))
    return out
