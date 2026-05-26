from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from ..config import get_settings
from ..hh_fallback import (
    hh_error_hint,
    is_hh_user_agent_rejected,
    load_demo_employers,
)
from ..models import Company, Competency, Escalation, EscalationStatus, PhaseKey, PhaseStatus, PhaseRun
from ..services import (
    create_escalation,
    ensure_workspace,
    get_phase_run,
    log_action,
    unlock_next_phase,
    update_phase,
)
from .hh_employers import employer_to_company_fields, search_employers
from .scoring import apply_score, industry_skill_set, score_company

logger = logging.getLogger(__name__)


def _company_dict(c: Company) -> dict:
    breakdown = {}
    if c.score_breakdown:
        try:
            breakdown = json.loads(c.score_breakdown)
        except json.JSONDecodeError:
            breakdown = {}
    return {
        "id": c.id,
        "name": c.name,
        "industry": c.industry,
        "region": c.region,
        "website": c.website,
        "description": c.description,
        "tech_stack": c.tech_stack,
        "employee_count": c.employee_count,
        "size_category": c.size_category,
        "has_education_program": c.has_education_program,
        "contact_name": c.contact_name,
        "contact_email": c.contact_email,
        "contact_role": c.contact_role,
        "contact_phone": c.contact_phone,
        "score": c.score,
        "score_breakdown": breakdown,
        "status": c.status,
        "in_shortlist": c.in_shortlist,
        "verified": c.verified,
        "notes": c.notes,
        "source": c.source,
    }


def list_companies(
    db: Session,
    *,
    limit: int = 100,
    status: str | None = None,
    shortlist_only: bool = False,
) -> list[dict]:
    ws = ensure_workspace(db)
    q = db.query(Company).filter(Company.workspace_id == ws.id)
    if status:
        q = q.filter(Company.status == status)
    if shortlist_only:
        q = q.filter(Company.in_shortlist.is_(True))
    rows = q.order_by(Company.score.desc().nullslast(), Company.name).limit(limit).all()
    return [_company_dict(c) for c in rows]


def get_top(db: Session, n: int) -> dict:
    ws = ensure_workspace(db)
    rows = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.status != "rejected")
        .order_by(Company.score.desc().nullslast())
        .limit(n)
        .all()
    )
    return {
        "limit": n,
        "total_in_workspace": db.query(Company).filter(Company.workspace_id == ws.id).count(),
        "companies": [_company_dict(c) for c in rows],
    }


def get_company(db: Session, company_id: int) -> dict:
    ws = ensure_workspace(db)
    c = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one()
    )
    return _company_dict(c)


def _rescore_workspace(db: Session, workspace_id: int) -> int:
    skills = industry_skill_set(
        db.query(Competency).filter(Competency.workspace_id == workspace_id).all()
    )
    companies = db.query(Company).filter(Company.workspace_id == workspace_id).all()
    for c in companies:
        if c.status == "rejected":
            continue
        apply_score(c, score_company(c, skills))
    db.commit()
    return len(companies)


def discover_employers(
    db: Session,
    *,
    actor_email: str,
    query: str | None = None,
    max_pages: int = 5,
) -> dict:
    settings = get_settings()
    ws = ensure_workspace(db)
    search_text = query or ws.industry or "IT компания"

    demo_mode = False
    hh_message: str | None = None
    if is_hh_user_agent_rejected(settings.hh_user_agent):
        demo_mode = True
        hh_message = (
            "В HH_USER_AGENT указан example.com — API hh.ru блокирует такой контакт. "
            "Используются демо-компании."
        )
        employers = load_demo_employers()
    else:
        try:
            employers = search_employers(
                user_agent=settings.hh_user_agent,
                text=search_text,
                area_id=settings.hh_default_area_id or None,
                max_pages=max_pages,
                access_token=settings.hh_access_token,
            )
        except Exception as exc:
            logger.warning("HH discover failed, demo fallback: %s", exc)
            demo_mode = True
            hh_message = hh_error_hint(exc)
            employers = load_demo_employers()

    added = 0
    for emp in employers:
        fields = employer_to_company_fields(emp, ws.industry or "IT")
        ext_id = fields.get("external_id")
        if ext_id:
            exists = (
                db.query(Company)
                .filter(Company.workspace_id == ws.id, Company.external_id == ext_id)
                .first()
            )
            if exists:
                continue
        db.add(Company(workspace_id=ws.id, **fields))
        added += 1

    db.commit()
    scored = _rescore_workspace(db, ws.id)

    progress = min(85, 10 + scored // 2)
    update_phase(
        db,
        PhaseKey.COMPANIES.value,
        actor_email=actor_email,
        progress_pct=progress,
        notes=f"Найдено работодателей: +{added}, всего: {scored}",
    )

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="companies.discover",
        details=f"query={search_text}, added={added}, total={scored}",
    )
    db.commit()

    if scored >= 10:
        _seed_escalation_2(db, ws.id)

    return {
        "added": added,
        "total": scored,
        "query": search_text,
        "demo_mode": demo_mode,
        "message": hh_message,
    }


def _seed_escalation_2(db: Session, workspace_id: int) -> None:
    phase = get_phase_run(db, workspace_id, PhaseKey.COMPANIES.value)
    if phase.status != PhaseStatus.ACTIVE.value:
        return
    exists = (
        db.query(Escalation)
        .filter(Escalation.workspace_id == workspace_id, Escalation.level == 2)
        .first()
    )
    if exists:
        return
    create_escalation(
        db,
        workspace_id=workspace_id,
        phase_key=PhaseKey.COMPANIES.value,
        level=2,
        title="Верифицируйте шорт-лист компаний",
        description="Просмотрите Top-20, отметьте подходящих партнёров и утвердите список.",
    )
    db.commit()


def update_company(db: Session, company_id: int, **fields) -> dict:
    ws = ensure_workspace(db)
    c = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one()
    )
    allowed = {
        "name", "industry", "region", "website", "description", "tech_stack",
        "employee_count", "size_category", "has_education_program",
        "contact_name", "contact_email", "contact_role", "contact_phone", "notes",
    }
    for key, val in fields.items():
        if key in allowed and val is not None:
            setattr(c, key, val)
    skills = industry_skill_set(
        db.query(Competency).filter(Competency.workspace_id == ws.id).all()
    )
    apply_score(c, score_company(c, skills))
    db.commit()
    db.refresh(c)
    return _company_dict(c)


def verify_company(db: Session, company_id: int, *, actor_email: str, shortlist: bool = True) -> dict:
    ws = ensure_workspace(db)
    c = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one()
    )
    c.verified = True
    c.in_shortlist = shortlist
    c.status = "shortlisted" if shortlist else "approved"
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="company.verify",
        entity_type="company",
        entity_id=str(company_id),
    )
    db.commit()
    db.refresh(c)
    return _company_dict(c)


def reject_company(db: Session, company_id: int, *, actor_email: str, reason: str = "") -> dict:
    ws = ensure_workspace(db)
    c = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one()
    )
    c.status = "rejected"
    c.in_shortlist = False
    c.verified = False
    c.notes = reason or c.notes
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="company.reject",
        entity_type="company",
        entity_id=str(company_id),
        details=reason,
    )
    db.commit()
    db.refresh(c)
    return _company_dict(c)


def bulk_add_shortlist(db: Session, *, actor_email: str, limit: int = 3) -> dict:
    ws = ensure_workspace(db)
    rows = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.status != "rejected")
        .order_by(Company.score.desc().nullslast())
        .limit(max(1, min(limit, 20)))
        .all()
    )
    if not rows:
        raise ValueError("нет компаний — сначала нажмите «Найти компании»")
    for c in rows:
        c.verified = True
        c.in_shortlist = True
        c.status = "shortlisted"
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="companies.bulk_shortlist",
        details=f"count={len(rows)}",
    )
    db.commit()
    return {
        "added": len(rows),
        "company_ids": [c.id for c in rows],
        "companies": [{"id": c.id, "name": c.name} for c in rows],
    }


def approve_shortlist(db: Session, *, actor_email: str) -> dict:
    from datetime import datetime, timezone

    ws = ensure_workspace(db)
    shortlist = (
        db.query(Company)
        .filter(
            Company.workspace_id == ws.id,
            Company.in_shortlist.is_(True),
            Company.status != "rejected",
        )
        .count()
    )
    if shortlist < 1:
        raise ValueError(
            "шорт-лист пуст — сначала «Top-3 в шорт-лист» или отметьте компании галочкой"
        )

    phase = get_phase_run(db, ws.id, PhaseKey.COMPANIES.value)
    if phase.status != PhaseStatus.COMPLETED.value:
        phase.status = PhaseStatus.COMPLETED.value
        phase.progress_pct = 100
        unlock_next_phase(db, PhaseKey.COMPANIES)

    comm_phase = get_phase_run(db, ws.id, PhaseKey.COMMUNICATION.value)
    if comm_phase.status == PhaseStatus.LOCKED.value:
        comm_phase.status = PhaseStatus.ACTIVE.value
        comm_phase.progress_pct = max(comm_phase.progress_pct, 10)

    for esc in (
        db.query(Escalation)
        .filter(
            Escalation.workspace_id == ws.id,
            Escalation.level == 2,
            Escalation.status == EscalationStatus.OPEN.value,
        )
        .all()
    ):
        esc.status = EscalationStatus.RESOLVED.value
        esc.resolved_by = actor_email
        esc.resolved_at = datetime.now(timezone.utc)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="shortlist.approve",
        details=f"count={shortlist}",
    )
    db.commit()
    return {"shortlist_count": shortlist, "status": "phase_completed"}
