from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..llm_client import generate_text
from ..models import (
    Communication,
    Company,
    Escalation,
    EscalationStatus,
    PhaseKey,
    PhaseStatus,
    PhaseRun,
    TouchPoint,
)
from ..services import (
    create_escalation,
    ensure_workspace,
    get_phase_run,
    log_action,
    unlock_next_phase,
    update_phase,
)
from ..config import get_settings
from .generator import (
    faq_fallback_body,
    faq_prompt,
    letter_prompt,
    letter_template,
    parse_subject_body,
    value_prop_prompt,
    value_prop_template,
)
from .history import list_versions, snapshot_version

logger = logging.getLogger(__name__)


def _comm_dict(c: Communication, company_name: str | None = None) -> dict:
    return {
        "id": c.id,
        "company_id": c.company_id,
        "company_name": company_name,
        "comm_type": c.comm_type,
        "tone": c.tone,
        "subject": c.subject,
        "body": c.body,
        "value_proposition": c.value_proposition,
        "status": c.status,
        "approved_by": c.approved_by,
        "approved_at": c.approved_at.isoformat() if c.approved_at else None,
        "version": c.version,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def get_faq(db: Session) -> dict | None:
    comm = (
        db.query(Communication)
        .filter(Communication.comm_type == "faq", Communication.company_id.is_(None))
        .order_by(Communication.created_at.desc())
        .first()
    )
    return _comm_dict(comm) if comm else None


def list_for_shortlist(db: Session) -> list[dict]:
    ws = ensure_workspace(db)
    companies = (
        db.query(Company)
        .filter(
            Company.workspace_id == ws.id,
            Company.in_shortlist.is_(True),
            Company.status != "rejected",
        )
        .order_by(Company.score.desc().nullslast())
        .all()
    )
    out: list[dict] = []
    for co in companies:
        comms = (
            db.query(Communication)
            .filter(Communication.company_id == co.id)
            .order_by(Communication.created_at.desc())
            .all()
        )
        touches = (
            db.query(TouchPoint)
            .filter(TouchPoint.company_id == co.id)
            .order_by(TouchPoint.step_order)
            .all()
        )
        out.append(
            {
                "company": {"id": co.id, "name": co.name, "score": co.score},
                "communications": [_comm_dict(c, co.name) for c in comms],
                "touch_plan": [
                    {
                        "id": t.id,
                        "step_order": t.step_order,
                        "title": t.title,
                        "days_after_start": t.days_after_start,
                        "channel": t.channel,
                        "status": t.status,
                    }
                    for t in touches
                ],
            }
        )
    return out


def generate_letter(
    db: Session,
    company_id: int,
    *,
    actor_email: str,
    tone: str = "formal",
) -> dict:
    ws = ensure_workspace(db)
    company = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one()
    )
    settings = get_settings()
    memory_hints = ""
    if settings.strategy_memory_enabled:
        from ..memory.strategy import get_strategy_hints

        memory_hints = get_strategy_hints(db, category="letter", tone=tone)

    base_prompt = letter_prompt(company, tone, ws.industry)
    if memory_hints:
        base_prompt = f"{memory_hints}\n\n---\n\n{base_prompt}"

    if settings.comms_use_llm:
        try:
            raw = generate_text(
                base_prompt,
                timeout_seconds=settings.comms_llm_timeout_seconds,
            )
            subject, body = parse_subject_body(raw)
            vp_raw = generate_text(
                value_prop_prompt(company, ws.industry),
                timeout_seconds=settings.comms_llm_timeout_seconds,
            )
        except Exception:
            subject, body = letter_template(company, tone, ws.industry)
            vp_raw = value_prop_template(company, ws.industry)
    else:
        subject, body = letter_template(company, tone, ws.industry)
        vp_raw = value_prop_template(company, ws.industry)
    comm = Communication(
        company_id=company.id,
        comm_type="letter",
        tone=tone,
        subject=subject,
        body=body,
        value_proposition=vp_raw,
        status="draft",
        version=1,
    )
    db.add(comm)
    db.flush()
    _ensure_touch_plan(db, company.id, comm.id)
    update_phase(
        db,
        PhaseKey.COMMUNICATION.value,
        actor_email=actor_email,
        progress_pct=min(80, 20 + len(list_for_shortlist(db)) * 15),
    )
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="comms.generate",
        entity_type="company",
        entity_id=str(company_id),
        details=f"tone={tone}",
    )
    db.commit()
    db.refresh(comm)
    _maybe_escalation_3(db, ws.id)
    return _comm_dict(comm, company.name)


def generate_batch(db: Session, *, actor_email: str, tone: str = "formal") -> dict:
    ws = ensure_workspace(db)
    companies = (
        db.query(Company)
        .filter(
            Company.workspace_id == ws.id,
            Company.in_shortlist.is_(True),
            Company.status != "rejected",
        )
        .all()
    )
    created = 0
    for co in companies:
        exists = (
            db.query(Communication)
            .filter(
                Communication.company_id == co.id,
                Communication.tone == tone,
                Communication.comm_type == "letter",
            )
            .first()
        )
        if exists:
            continue
        generate_letter(db, co.id, actor_email=actor_email, tone=tone)
        created += 1
    return {"generated": created, "tone": tone}


def generate_faq(db: Session, *, actor_email: str) -> dict:
    ws = ensure_workspace(db)
    existing = (
        db.query(Communication)
        .filter(Communication.comm_type == "faq", Communication.company_id.is_(None))
        .first()
    )
    if existing:
        return _comm_dict(existing)

    settings = get_settings()
    if settings.comms_use_llm:
        try:
            body = generate_text(
                faq_prompt(ws.industry),
                timeout_seconds=settings.comms_llm_timeout_seconds,
            )
            if not body.strip() or "Черновик сгенерирован без LLM" in body:
                body = faq_fallback_body()
        except Exception:
            body = faq_fallback_body()
    else:
        body = faq_fallback_body()
    comm = Communication(
        company_id=None,
        comm_type="faq",
        tone="formal",
        subject="FAQ для партнёров ПроКомпетенции",
        body=body,
        status="draft",
    )
    db.add(comm)
    log_action(db, workspace_id=ws.id, actor_email=actor_email, action="comms.faq")
    db.commit()
    db.refresh(comm)
    return _comm_dict(comm)


def update_communication(
    db: Session,
    comm_id: int,
    *,
    actor_email: str | None = None,
    subject: str | None = None,
    body: str | None = None,
    value_proposition: str | None = None,
) -> dict:
    comm = db.query(Communication).filter(Communication.id == comm_id).one()
    snapshot_version(db, comm, edited_by=actor_email)
    if subject is not None:
        comm.subject = subject
    if body is not None:
        comm.body = body
    if value_proposition is not None:
        comm.value_proposition = value_proposition
    comm.version += 1
    comm.status = "draft"
    db.commit()
    db.refresh(comm)
    name = None
    if comm.company_id:
        co = db.query(Company).filter(Company.id == comm.company_id).first()
        name = co.name if co else None
    return _comm_dict(comm, name)


def get_communication_versions(db: Session, comm_id: int) -> list[dict]:
    db.query(Communication).filter(Communication.id == comm_id).one()
    return list_versions(db, comm_id)


def approve_communication(db: Session, comm_id: int, *, actor_email: str) -> dict:
    comm = db.query(Communication).filter(Communication.id == comm_id).one()
    comm.status = "approved"
    comm.approved_by = actor_email
    comm.approved_at = datetime.now(timezone.utc)
    ws = ensure_workspace(db)
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="comms.approve",
        entity_id=str(comm_id),
    )
    db.commit()
    db.refresh(comm)
    name = None
    if comm.company_id:
        co = db.query(Company).filter(Company.id == comm.company_id).first()
        name = co.name if co else None
    return _comm_dict(comm, name)


def approve_all_ready(db: Session, *, actor_email: str) -> dict:
    ws = ensure_workspace(db)
    approved = (
        db.query(Communication)
        .join(Company, Communication.company_id == Company.id)
        .filter(
            Company.workspace_id == ws.id,
            Company.in_shortlist.is_(True),
            Communication.comm_type == "letter",
            Communication.status == "approved",
        )
        .count()
    )
    shortlist = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.in_shortlist.is_(True))
        .count()
    )
    if approved < 1:
        raise ValueError("approve at least one letter before completing phase")

    phase = get_phase_run(db, ws.id, PhaseKey.COMMUNICATION.value)
    phase.status = PhaseStatus.COMPLETED.value
    phase.progress_pct = 100
    unlock_next_phase(db, PhaseKey.COMMUNICATION)

    outreach_phase = get_phase_run(db, ws.id, PhaseKey.OUTREACH.value)
    if outreach_phase.status == PhaseStatus.LOCKED.value:
        outreach_phase.status = PhaseStatus.ACTIVE.value
        outreach_phase.progress_pct = 10

    for esc in (
        db.query(Escalation)
        .filter(
            Escalation.workspace_id == ws.id,
            Escalation.level == 3,
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
        action="comms.phase_complete",
        details=f"approved={approved}/{shortlist}",
    )
    db.commit()
    return {"approved_letters": approved, "shortlist": shortlist}


def _ensure_touch_plan(db: Session, company_id: int, first_comm_id: int) -> None:
    exists = db.query(TouchPoint).filter(TouchPoint.company_id == company_id).first()
    if exists:
        return
    steps = [
        (0, "Первичное письмо", 0, first_comm_id),
        (1, "Follow-up #1", 7, None),
        (2, "Follow-up #2", 14, None),
    ]
    for order, title, days, cid in steps:
        db.add(
            TouchPoint(
                company_id=company_id,
                communication_id=cid,
                step_order=order,
                title=title,
                days_after_start=days,
                channel="email",
                status="planned" if order > 0 else "ready",
            )
        )


def _maybe_escalation_3(db: Session, workspace_id: int) -> None:
    phase = get_phase_run(db, workspace_id, PhaseKey.COMMUNICATION.value)
    if phase.status != PhaseStatus.ACTIVE.value:
        return
    drafts = (
        db.query(Communication)
        .filter(Communication.status == "draft", Communication.comm_type == "letter")
        .count()
    )
    if drafts < 1:
        return
    if (
        db.query(Escalation)
        .filter(Escalation.workspace_id == workspace_id, Escalation.level == 3)
        .first()
    ):
        return
    create_escalation(
        db,
        workspace_id=workspace_id,
        phase_key=PhaseKey.COMMUNICATION.value,
        level=3,
        title="Утвердите тексты писем",
        description="Проверьте черновики для компаний из шорт-листа и одобрите отправку.",
    )
    db.commit()
