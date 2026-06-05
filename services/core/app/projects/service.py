from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..llm_client import generate_text
from ..models import (
    Company,
    Competency,
    PartnerAgreement,
    PartnershipCycle,
    PhaseKey,
    PhaseRun,
    PhaseStatus,
    Project,
    ProjectRole,
    ProjectTeamClaim,
    ProjectTeamInterview,
)
from ..config import get_settings
from ..cycles.service import get_phase_run, get_work_context
from ..profiles.service import display_name
from .interviews import list_pending_interviews
from ..services import log_action
from .catalog import (
    CATALOG_MODE_PERMANENT,
    CATALOG_MODE_TEMPORARY,
    catalog_visible_filter,
    resolve_catalog_until,
)
from .limits import MAX_TEAM_MEMBERS, clamp_team_size, validate_catalog_publish_params
from .generator import competencies_for_workspace, parse_tz_response, tz_prompt
from .roles import list_project_roles, sync_roles_from_spec
from .enrollment import (
    active_enrollment_count,
    enroll_student,
    get_student_enrollment,
    list_my_enrollments,
    withdraw_enrollment,
)
from .team_claims import catalog_teams_meta, list_project_claims, viewer_team_context


def _project_publish_meta(p: Project) -> dict:
    try:
        validate_catalog_publish_params(p)
        ready, reason = True, None
    except ValueError as exc:
        ready, reason = False, str(exc)

    expiry_soon = None
    mode = getattr(p, "catalog_mode", CATALOG_MODE_PERMANENT) or CATALOG_MODE_PERMANENT
    if p.catalog_visible and mode == CATALOG_MODE_TEMPORARY and p.catalog_visible_until:
        now = datetime.now(timezone.utc)
        until = p.catalog_visible_until
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if until > now:
            days_left = (until - now).days
            if days_left <= get_settings().catalog_expiry_reminder_days_before:
                expiry_soon = {
                    "days_left": days_left,
                    "until": until.isoformat(),
                }

    return {
        "publish_ready": ready,
        "publish_block_reason": reason,
        "catalog_expiry_soon": expiry_soon,
        "can_extend_catalog": mode == CATALOG_MODE_TEMPORARY
        and p.status == "approved"
        and (p.catalog_visible or p.published_at is not None),
    }


def _norm_email(email: str | None) -> str:
    return (email or "").strip().lower()


def _can_delete_project(cycle, *, actor_email: str, actor_role: str) -> bool:
    if actor_role == "admin":
        return True
    return _norm_email(cycle.created_by) == _norm_email(actor_email)


def _project_dict(p: Project, company_name: str | None = None, db: Session | None = None) -> dict:
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
        "max_teams": getattr(p, "max_teams", None) or 3,
        "interview_required": bool(getattr(p, "interview_required", False)),
        "duration_weeks": p.duration_weeks,
        "status": p.status,
        "catalog_visible": p.catalog_visible,
        "catalog_mode": getattr(p, "catalog_mode", CATALOG_MODE_PERMANENT) or CATALOG_MODE_PERMANENT,
        "catalog_visible_until": (
            p.catalog_visible_until.isoformat() if p.catalog_visible_until else None
        ),
        "approved_by": p.approved_by,
        "approved_by_fio": display_name(db, p.approved_by) if db and p.approved_by else None,
        "approved_at": p.approved_at.isoformat() if p.approved_at else None,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        **_project_publish_meta(p),
    }


def dashboard(
    db: Session,
    *,
    actor_email: str | None = None,
    actor_role: str | None = None,
) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    cycle = ctx.cycle
    allow_delete = _can_delete_project(
        cycle,
        actor_email=actor_email or "",
        actor_role=actor_role or "",
    )
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
        "projects": [
            {
                **_project_dict(p, company_map.get(p.company_id or 0), db),
                "claimed_teams": list_project_claims(db, p.id),
                "can_delete": allow_delete,
            }
            for p in projects
        ],
        "pending_interviews": list_pending_interviews(db, cid),
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
    project.team_size = clamp_team_size(team_size, default=4)
    project.max_teams = 3
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
    return _project_dict(project, company.name, db)


def update_project(
    db: Session,
    project_id: int,
    *,
    actor_email: str,
    title: str | None = None,
    spec_markdown: str | None = None,
    team_size: int | None = None,
    max_teams: int | None = None,
    interview_required: bool | None = None,
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
        project.team_size = clamp_team_size(team_size)
    if max_teams is not None:
        if max_teams < 1 or max_teams > 50:
            raise ValueError("max_teams must be 1..50")
        project.max_teams = max_teams
    if interview_required is not None:
        project.interview_required = interview_required
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
    return _project_dict(project, company_name, db)


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
    return _project_dict(project, company_name, db)


def publish_to_catalog(
    db: Session,
    project_id: int,
    *,
    actor_email: str,
    catalog_mode: str = CATALOG_MODE_PERMANENT,
    catalog_months: int | None = None,
    catalog_until: datetime | None = None,
) -> dict:
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

    validate_catalog_publish_params(project)

    project.catalog_mode = (catalog_mode or CATALOG_MODE_PERMANENT).strip().lower()
    if project.catalog_mode not in (CATALOG_MODE_PERMANENT, CATALOG_MODE_TEMPORARY):
        raise ValueError("catalog_mode must be permanent or temporary")
    project.catalog_visible_until = resolve_catalog_until(
        catalog_mode=project.catalog_mode,
        catalog_months=catalog_months,
        catalog_until=catalog_until,
    )
    project.catalog_visible = True
    project.published_at = datetime.now(timezone.utc)
    sync_roles_from_spec(db, project)

    published_count = (
        db.query(Project)
        .filter(Project.cycle_id == cid, *catalog_visible_filter())
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
    return _project_dict(project, company_name, db)


def _matches_competencies(project: Project, filters: list[str]) -> bool:
    if not filters:
        return True
    haystack = (project.competencies or "").lower()
    return any(needle in haystack for needle in filters)


def _catalog_meta(db: Session, project: Project) -> dict:
    return {
        **catalog_teams_meta(db, project),
        "claimed_teams": list_project_claims(db, project.id),
    }


def list_catalog(db: Session, *, competencies: list[str] | None = None) -> list[dict]:
    from ..models import PartnershipCycle

    needles = [c.strip().lower() for c in (competencies or []) if c.strip()]
    rows = (
        db.query(Project, Company, PartnershipCycle)
        .outerjoin(Company, Project.company_id == Company.id)
        .join(PartnershipCycle, Project.cycle_id == PartnershipCycle.id)
        .filter(*catalog_visible_filter())
        .order_by(Project.published_at.desc())
        .all()
    )
    out: list[dict] = []
    for proj, co, cycle in rows:
        if not _matches_competencies(proj, needles):
            continue
        item = _project_dict(proj, co.name if co else None, db)
        item["cycle_id"] = cycle.id
        item["cycle_name"] = cycle.name
        item.pop("spec_markdown", None)
        item.update(_catalog_meta(db, proj))
        out.append(item)
    return out


def get_catalog_project(
    db: Session, project_id: int, *, viewer_email: str | None = None
) -> dict:
    from ..models import PartnershipCycle

    row = (
        db.query(Project, Company, PartnershipCycle)
        .outerjoin(Company, Project.company_id == Company.id)
        .join(PartnershipCycle, Project.cycle_id == PartnershipCycle.id)
        .filter(Project.id == project_id, *catalog_visible_filter())
        .one()
    )
    proj, co, cycle = row
    data = _project_dict(proj, co.name if co else None, db)
    data["cycle_id"] = cycle.id
    data["cycle_name"] = cycle.name
    data.update(_catalog_meta(db, proj))
    data["roles"] = list_project_roles(db, proj.id)
    data.update(viewer_team_context(db, project_id, viewer_email=viewer_email))

    if viewer_email:
        claim = data.get("my_team_claim")
        if claim and claim.get("project_id") == project_id and claim.get("status") == "active":
            enrollment = get_student_enrollment(db, proj.id, viewer_email.lower())
            data["my_enrollment"] = {
                "id": enrollment.id if enrollment else None,
                "team_id": claim.get("team_id"),
                "status": "active",
                "via_team": True,
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
    return _project_dict(project, company_name, db)


def complete_projects_phase(db: Session, *, actor_email: str) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    published = (
        db.query(Project)
        .filter(Project.cycle_id == cid, *catalog_visible_filter())
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


def delete_project(
    db: Session,
    project_id: int,
    *,
    actor_email: str,
    actor_role: str,
    from_catalog: bool = False,
) -> dict:
    if actor_role == "admin":
        project = db.query(Project).filter(Project.id == project_id).one()
        cycle = (
            db.query(PartnershipCycle)
            .filter(PartnershipCycle.id == project.cycle_id)
            .one()
        )
        workspace_id = project.workspace_id
    else:
        ctx = get_work_context(db)
        cycle = ctx.cycle
        workspace_id = ctx.workspace.id
        project = (
            db.query(Project)
            .filter(Project.cycle_id == ctx.cycle_id, Project.id == project_id)
            .one()
        )
        if not _can_delete_project(cycle, actor_email=actor_email, actor_role=actor_role):
            raise ValueError(
                "удалять проект может владелец цикла; модерация может удалить любой проект"
            )

    if from_catalog and actor_role != "admin":
        raise ValueError("удалять из каталога может только модерация")

    title = project.title
    db.query(ProjectTeamInterview).filter(
        ProjectTeamInterview.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(ProjectTeamClaim).filter(ProjectTeamClaim.project_id == project_id).delete(
        synchronize_session=False
    )
    db.delete(project)
    log_action(
        db,
        workspace_id=workspace_id,
        actor_email=actor_email,
        action="projects.catalog.delete" if from_catalog else "projects.delete",
        entity_type="project",
        entity_id=str(project_id),
        details=title[:200],
    )
    db.commit()
    return {"status": "deleted", "project_id": project_id}
