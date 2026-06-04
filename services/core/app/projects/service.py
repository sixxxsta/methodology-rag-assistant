from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..llm_client import generate_text
from ..models import (
    Company,
    Competency,
    PartnerAgreement,
    PhaseKey,
    PhaseRun,
    PhaseStatus,
    Project,
    ProjectRole,
)
from ..cycles.service import get_phase_run, get_work_context
from ..services import log_action
from ..services import log_action
from .generator import competencies_for_workspace, parse_tz_response, tz_prompt
from .roles import list_project_roles, sync_roles_from_spec
from .enrollment import (
    active_enrollment_count,
    enroll_student,
    get_student_enrollment,
    list_my_enrollments,
    withdraw_enrollment,
)


def _project_dict(p: Project, company_name: str | None = None) -> dict:
    return {
        "id": p.id,
        "company_id": p.company_id,
        "company_name": company_name,
        "agreement_id": p.agreement_id,
        "title": p.title,
        "description": p.description,
        "spec_markdown": p.spec_markdown,
        "competencies": p.competencies,
        "team_size": p.team_size,
        "duration_weeks": p.duration_weeks,
        "status": p.status,
        "catalog_visible": p.catalog_visible,
        "approved_by": p.approved_by,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def dashboard(db: Session) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    partners = (
        db.query(Company)
        .filter(Company.cycle_id == cid, Company.status == "partner")
        .order_by(Company.name)
        .all()
    )
    agreements = (
        db.query(PartnerAgreement)
        .join(Company, PartnerAgreement.company_id == Company.id)
        .filter(Company.cycle_id == cid)
        .order_by(PartnerAgreement.created_at.desc())
        .all()
    )
    projects = (
        db.query(Project)
        .filter(Project.cycle_id == cid)
        .order_by(Project.updated_at.desc())
        .all()
    )
    company_map = {c.id: c.name for c in partners}
    for a in agreements:
        co = db.query(Company).filter(Company.id == a.company_id).one()
        company_map[co.id] = co.name

    pending_partners: list[dict] = []
    for agr in agreements:
        existing = next((p for p in projects if p.agreement_id == agr.id), None)
        co = db.query(Company).filter(Company.id == agr.company_id).one()
        pending_partners.append(
            {
                "company_id": co.id,
                "company_name": co.name,
                "agreement_id": agr.id,
                "agreement_summary": agr.summary[:200],
                "project_id": existing.id if existing else None,
                "project_status": existing.status if existing else None,
            }
        )

    published = sum(1 for p in projects if p.catalog_visible)
    draft = sum(1 for p in projects if p.status == "draft")
    approved = sum(1 for p in projects if p.status == "approved")

    phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)

    return {
        "phase_status": phase.status,
        "phase_progress": phase.progress_pct,
        "partners_count": len({a.company_id for a in agreements}),
        "projects_total": len(projects),
        "projects_draft": draft,
        "projects_approved": approved,
        "catalog_published": published,
        "pending": pending_partners,
        "projects": [_project_dict(p, company_map.get(p.company_id or 0)) for p in projects],
    }


def generate_project(
    db: Session,
    company_id: int,
    *,
    actor_email: str,
    agreement_id: int | None = None,
) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    company = (
        db.query(Company)
        .filter(Company.cycle_id == cid, Company.id == company_id)
        .one()
    )
    agr_q = db.query(PartnerAgreement).filter(PartnerAgreement.company_id == company.id)
    if agreement_id:
        agr_q = agr_q.filter(PartnerAgreement.id == agreement_id)
    agreement = agr_q.order_by(PartnerAgreement.created_at.desc()).first()
    if not agreement:
        raise ValueError("no partner agreement for this company")

    comps = (
        db.query(Competency)
        .filter(Competency.cycle_id == cid)
        .all()
    )
    top_skills = competencies_for_workspace(comps)

    prompt = tz_prompt(
        company,
        agreement,
        industry=ws.industry,
        top_competencies=top_skills,
    )
    raw = generate_text(prompt, context=f"Компания: {company.name}")
    title, spec, team_size, duration_weeks, comp_csv = parse_tz_response(raw)

    project = (
        db.query(Project)
        .filter(
            Project.cycle_id == cid,
            Project.agreement_id == agreement.id,
        )
        .first()
    )
    if not project:
        project = Project(
            workspace_id=ws.id,
            cycle_id=cid,
            company_id=company.id,
            agreement_id=agreement.id,
            title=title,
            status="draft",
        )
        db.add(project)
    else:
        project.title = title

    project.spec_markdown = spec
    project.description = spec[:500] if spec else None
    project.team_size = team_size or 4
    project.duration_weeks = duration_weeks or 12
    project.competencies = comp_csv
    project.status = "draft"
    project.catalog_visible = False
    project.approved_by = None
    project.approved_at = None
    project.published_at = None

    phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)
    if phase.status == PhaseStatus.ACTIVE.value and phase.progress_pct < 50:
        phase.progress_pct = min(50, phase.progress_pct + 20)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.generate",
        entity_id=str(project.id if project.id else company_id),
    )
    db.commit()
    db.refresh(project)
    sync_roles_from_spec(db, project)
    db.commit()
    return _project_dict(project, company.name)


def update_project(
    db: Session,
    project_id: int,
    *,
    actor_email: str,
    title: str | None = None,
    spec_markdown: str | None = None,
    team_size: int | None = None,
    duration_weeks: int | None = None,
    competencies: str | None = None,
) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    project = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.id == project_id)
        .one()
    )
    if title is not None:
        project.title = title
    if spec_markdown is not None:
        project.spec_markdown = spec_markdown
        project.description = spec_markdown[:500]
    if team_size is not None:
        project.team_size = team_size
    if duration_weeks is not None:
        project.duration_weeks = duration_weeks
    if competencies is not None:
        project.competencies = competencies

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.update",
        entity_id=str(project_id),
    )
    db.commit()
    db.refresh(project)
    company_name = None
    if project.company_id:
        co = db.query(Company).filter(Company.id == project.company_id).one_or_none()
        company_name = co.name if co else None
    return _project_dict(project, company_name)


def approve_project(db: Session, project_id: int, *, actor_email: str) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    project = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.id == project_id)
        .one()
    )
    if not project.spec_markdown:
        raise ValueError("generate TZ before approval")

    project.status = "approved"
    project.approved_by = actor_email
    project.approved_at = datetime.now(timezone.utc)

    phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)
    if phase.status == PhaseStatus.ACTIVE.value:
        phase.progress_pct = max(phase.progress_pct, 70)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.approve",
        entity_id=str(project_id),
    )
    db.commit()
    db.refresh(project)
    company_name = None
    if project.company_id:
        co = db.query(Company).filter(Company.id == project.company_id).one_or_none()
        company_name = co.name if co else None
    return _project_dict(project, company_name)


def publish_to_catalog(db: Session, project_id: int, *, actor_email: str) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    project = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.id == project_id)
        .one()
    )
    if project.status != "approved":
        raise ValueError("approve project before publishing")

    project.catalog_visible = True
    project.published_at = datetime.now(timezone.utc)
    sync_roles_from_spec(db, project)

    published_count = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.catalog_visible.is_(True))
        .count()
    )

    phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)
    if phase.status == PhaseStatus.ACTIVE.value:
        phase.progress_pct = min(100, 50 + published_count * 15)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.publish",
        entity_id=str(project_id),
    )
    db.commit()
    db.refresh(project)
    company_name = None
    if project.company_id:
        co = db.query(Company).filter(Company.id == project.company_id).one_or_none()
        company_name = co.name if co else None
    return _project_dict(project, company_name)


def _matches_competencies(project: Project, filters: list[str]) -> bool:
    if not filters:
        return True
    haystack = (project.competencies or "").lower()
    return any(needle in haystack for needle in filters)


def _catalog_meta(db: Session, project: Project) -> dict:
    team_size = project.team_size or 4
    enrolled = active_enrollment_count(db, project.id)
    return {
        "enrollment_count": enrolled,
        "seats_left": max(0, team_size - enrolled),
        "team_size": team_size,
    }


def list_catalog(db: Session, *, competencies: list[str] | None = None) -> list[dict]:
    from ..models import PartnershipCycle

    needles = [c.strip().lower() for c in (competencies or []) if c.strip()]
    rows = (
        db.query(Project, Company, PartnershipCycle)
        .outerjoin(Company, Project.company_id == Company.id)
        .join(PartnershipCycle, Project.cycle_id == PartnershipCycle.id)
        .filter(Project.catalog_visible.is_(True))
        .order_by(Project.published_at.desc())
        .all()
    )
    out: list[dict] = []
    for proj, co, cycle in rows:
        if not _matches_competencies(proj, needles):
            continue
        item = _project_dict(proj, co.name if co else None)
        item["cycle_id"] = cycle.id
        item["cycle_name"] = cycle.name
        item.pop("spec_markdown", None)
        item.update(_catalog_meta(db, proj))
        out.append(item)
    return out


def get_catalog_project(
    db: Session, project_id: int, *, viewer_email: str | None = None
) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    row = (
        db.query(Project, Company)
        .outerjoin(Company, Project.company_id == Company.id)
        .filter(
            Project.cycle_id == cid,
            Project.id == project_id,
            Project.catalog_visible.is_(True),
        )
        .one()
    )
    proj, co = row
    data = _project_dict(proj, co.name if co else None)
    data.update(_catalog_meta(db, proj))
    data["roles"] = list_project_roles(db, proj.id)

    if viewer_email:
        enrollment = get_student_enrollment(db, proj.id, viewer_email.lower())
        if enrollment and enrollment.status == "active":
            role_title = None
            if enrollment.role_id:
                role = db.query(ProjectRole).filter(ProjectRole.id == enrollment.role_id).one_or_none()
                role_title = role.title if role else None
            data["my_enrollment"] = {
                "id": enrollment.id,
                "role_id": enrollment.role_id,
                "role_title": role_title,
                "status": enrollment.status,
            }
        else:
            data["my_enrollment"] = None

    return data


def get_project(db: Session, project_id: int) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    project = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.id == project_id)
        .one()
    )
    company_name = None
    if project.company_id:
        co = db.query(Company).filter(Company.id == project.company_id).one_or_none()
        company_name = co.name if co else None
    return _project_dict(project, company_name)


def complete_projects_phase(db: Session, *, actor_email: str) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    published = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.catalog_visible.is_(True))
        .count()
    )
    if published < 1:
        raise ValueError("publish at least one project to catalog")

    phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)
    phase.status = PhaseStatus.COMPLETED.value
    phase.progress_pct = 100

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.phase.complete",
    )
    db.commit()
    return {"status": "completed", "catalog_published": published}


def resync_project_roles(db: Session, project_id: int, *, actor_email: str) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    project = (
        db.query(Project)
        .filter(Project.cycle_id == cid, Project.id == project_id)
        .one()
    )
    roles = sync_roles_from_spec(db, project)
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="projects.roles.sync",
        entity_id=str(project_id),
    )
    db.commit()
    return {"roles": roles}
