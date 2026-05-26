from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import (
    Communication,
    Company,
    Escalation,
    EscalationStatus,
    Interaction,
    PartnerAgreement,
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
from .classifier import auto_reply_for, classify_response
from .mailer import send_email, smtp_configured

logger = logging.getLogger(__name__)


def _comm_out(comm: Communication, company: Company) -> dict:
    return {
        "id": comm.id,
        "company_id": company.id,
        "company_name": company.name,
        "contact_email": company.contact_email,
        "subject": comm.subject,
        "body": comm.body,
        "status": comm.status,
        "delivery_status": comm.delivery_status,
        "sent_at": comm.sent_at.isoformat() if comm.sent_at else None,
        "delivered_at": comm.delivered_at.isoformat() if comm.delivered_at else None,
        "opened_at": comm.opened_at.isoformat() if comm.opened_at else None,
    }


def dashboard(db: Session) -> dict:
    ws = ensure_workspace(db)
    approved = (
        db.query(Communication)
        .join(Company, Communication.company_id == Company.id)
        .filter(
            Company.workspace_id == ws.id,
            Communication.status == "approved",
            Communication.comm_type == "letter",
        )
        .all()
    )
    sent = sum(1 for c in approved if c.delivery_status in ("sent", "delivered", "opened"))
    pending = len(approved) - sent

    responses = (
        db.query(Interaction)
        .join(Company, Interaction.company_id == Company.id)
        .filter(Company.workspace_id == ws.id, Interaction.direction == "inbound")
        .order_by(Interaction.created_at.desc())
        .limit(50)
        .all()
    )

    due_followups = _due_touchpoints(db, ws.id)

    companies = (
        db.query(Company)
        .filter(
            Company.workspace_id == ws.id,
            Company.status != "rejected",
        )
        .order_by(Company.in_shortlist.desc(), Company.score.desc().nullslast())
        .limit(50)
        .all()
    )

    return {
        "smtp_enabled": smtp_configured(),
        "companies": [
            {
                "id": c.id,
                "name": c.name,
                "in_shortlist": c.in_shortlist,
                "status": c.status,
            }
            for c in companies
        ],
        "letters_approved": len(approved),
        "letters_sent": sent,
        "letters_pending": pending,
        "inbound_count": len(responses),
        "followups_due": len(due_followups),
        "queue": [_queue_item(db, c) for c in approved if c.delivery_status == "pending"],
        "recent_responses": [_interaction_dict(db, i) for i in responses[:20]],
        "followups": due_followups,
    }


def _queue_item(db: Session, comm: Communication) -> dict:
    company = db.query(Company).filter(Company.id == comm.company_id).one()
    return _comm_out(comm, company)


def _interaction_dict(db: Session, i: Interaction) -> dict:
    company = db.query(Company).filter(Company.id == i.company_id).one()
    return {
        "id": i.id,
        "company_id": i.company_id,
        "company_name": company.name,
        "subject": i.subject,
        "body": i.body,
        "classification": i.classification,
        "auto_handled": i.auto_handled,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


def send_letter(
    db: Session,
    comm_id: int,
    *,
    actor_email: str,
    use_smtp: bool = True,
) -> dict:
    comm = db.query(Communication).filter(Communication.id == comm_id).one()
    if comm.status != "approved":
        raise ValueError("letter must be approved before send")
    company = db.query(Company).filter(Company.id == comm.company_id).one()
    ws = ensure_workspace(db)

    if use_smtp and smtp_configured():
        if not company.contact_email:
            raise ValueError("company has no contact email")
        send_email(to=company.contact_email, subject=comm.subject, body=comm.body)
        comm.delivery_status = "sent"
    else:
        comm.delivery_status = "sent_manual"

    now = datetime.now(timezone.utc)
    comm.sent_at = now
    comm.delivered_at = now
    comm.status = "sent"

    tp = (
        db.query(TouchPoint)
        .filter(TouchPoint.company_id == company.id, TouchPoint.step_order == 0)
        .first()
    )
    if tp:
        tp.status = "completed"
        tp.completed_at = now
        if not tp.scheduled_at:
            tp.scheduled_at = now
        _schedule_followups(db, company.id, now)

    db.add(
        Interaction(
            company_id=company.id,
            communication_id=comm.id,
            channel="email",
            direction="outbound",
            subject=comm.subject,
            body=comm.body[:2000],
            outcome="sent",
        )
    )

    sent_count = (
        db.query(Communication)
        .join(Company, Communication.company_id == Company.id)
        .filter(
            Company.workspace_id == ws.id,
            Communication.delivery_status.in_(("sent", "sent_manual", "delivered", "opened")),
        )
        .count()
    )
    update_phase(
        db,
        PhaseKey.OUTREACH.value,
        actor_email=actor_email,
        progress_pct=min(90, 30 + sent_count * 10),
    )
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="outreach.send",
        entity_id=str(comm_id),
        details=f"smtp={use_smtp and smtp_configured()}",
    )
    db.commit()
    db.refresh(comm)
    return _comm_out(comm, company)


def _schedule_followups(db: Session, company_id: int, start: datetime) -> None:
    for tp in (
        db.query(TouchPoint)
        .filter(TouchPoint.company_id == company_id, TouchPoint.step_order > 0)
        .all()
    ):
        if tp.status == "planned" and not tp.scheduled_at:
            tp.scheduled_at = start + timedelta(days=tp.days_after_start)


def _due_touchpoints(db: Session, workspace_id: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    items: list[dict] = []
    companies = (
        db.query(Company)
        .filter(Company.workspace_id == workspace_id, Company.in_shortlist.is_(True))
        .all()
    )
    for co in companies:
        for tp in (
            db.query(TouchPoint)
            .filter(
                TouchPoint.company_id == co.id,
                TouchPoint.status == "planned",
                TouchPoint.step_order > 0,
            )
            .all()
        ):
            if tp.scheduled_at and tp.scheduled_at <= now:
                items.append(
                    {
                        "touch_id": tp.id,
                        "company_id": co.id,
                        "company_name": co.name,
                        "title": tp.title,
                        "days_after_start": tp.days_after_start,
                    }
                )
    return items


def send_followup(db: Session, touch_id: int, *, actor_email: str) -> dict:
    from ..llm_client import generate_text

    tp = db.query(TouchPoint).filter(TouchPoint.id == touch_id).one()
    company = db.query(Company).filter(Company.id == tp.company_id).one()
    ws = ensure_workspace(db)

    prompt = f"""Напиши короткое follow-up письмо (напоминание) для {company.name}.
Контекст: ранее отправляли приглашение к партнёрству с УрФУ, ответа не было.
Тон вежливый, 5-8 предложений, call-to-action — короткий созвон."""
    body = generate_text(prompt)
    subject = f"Re: Партнёрство УрФУ — {company.name}"

    comm = Communication(
        company_id=company.id,
        comm_type="followup",
        tone="formal",
        subject=subject,
        body=body,
        status="sent",
        delivery_status="sent_manual",
        sent_at=datetime.now(timezone.utc),
    )
    db.add(comm)
    tp.status = "completed"
    tp.completed_at = datetime.now(timezone.utc)

    log_action(db, workspace_id=ws.id, actor_email=actor_email, action="outreach.followup")
    db.commit()
    return {"touch_id": touch_id, "company_name": company.name, "subject": subject}


def record_inbound(
    db: Session,
    company_id: int,
    *,
    actor_email: str,
    subject: str,
    body: str,
    auto_respond: bool = True,
) -> dict:
    ws = ensure_workspace(db)
    company = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one_or_none()
    )
    if not company:
        raise ValueError(
            f"компания с id={company_id} не найдена. Выберите компанию из списка на странице «Компании»."
        )
    classification = classify_response(subject, body)
    auto_handled = False
    auto_reply = None

    if auto_respond:
        auto_reply = auto_reply_for(classification, body)
        if auto_reply:
            auto_handled = True
            db.add(
                Interaction(
                    company_id=company.id,
                    channel="email",
                    direction="outbound",
                    subject=f"Re: {subject}"[:512],
                    body=auto_reply,
                    outcome="auto_reply",
                    classification="auto",
                    auto_handled=True,
                )
            )

    interaction = Interaction(
        company_id=company.id,
        channel="email",
        direction="inbound",
        subject=subject[:512],
        body=body,
        classification=classification,
        auto_handled=auto_handled,
    )
    db.add(interaction)

    if classification in ("interest", "meeting_request"):
        _escalation_4(db, ws.id, company.name, classification)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="outreach.inbound",
        entity_id=str(company_id),
        details=classification,
    )
    db.commit()
    db.refresh(interaction)
    return {
        **_interaction_dict(db, interaction),
        "auto_reply": auto_reply,
        "needs_human": classification in ("interest", "meeting_request"),
    }


def _escalation_4(db: Session, workspace_id: int, company_name: str, kind: str) -> None:
    if (
        db.query(Escalation)
        .filter(
            Escalation.workspace_id == workspace_id,
            Escalation.level == 4,
            Escalation.status == EscalationStatus.OPEN.value,
        )
        .first()
    ):
        return
    create_escalation(
        db,
        workspace_id=workspace_id,
        phase_key=PhaseKey.OUTREACH.value,
        level=4,
        title=f"Требуется личный контакт: {company_name}",
        description=f"Получен ответ ({kind}). Вступите в диалог с представителем компании.",
    )
    db.commit()


def record_agreement(
    db: Session,
    company_id: int,
    *,
    actor_email: str,
    summary: str,
    status: str = "agreed",
) -> dict:
    ws = ensure_workspace(db)
    company = (
        db.query(Company)
        .filter(Company.workspace_id == ws.id, Company.id == company_id)
        .one_or_none()
    )
    if not company:
        raise ValueError(
            f"компания с id={company_id} не найдена. Сначала найдите компании (фаза 2) и добавьте в шорт-лист."
        )
    agr = PartnerAgreement(
        company_id=company.id,
        summary=summary,
        status=status,
        recorded_by=actor_email,
    )
    db.add(agr)
    company.status = "partner"

    phase = get_phase_run(db, ws.id, PhaseKey.OUTREACH.value)
    if phase.status == PhaseStatus.ACTIVE.value:
        phase.progress_pct = 100
        phase.status = PhaseStatus.COMPLETED.value
        unlock_next_phase(db, PhaseKey.OUTREACH)

    projects_phase = get_phase_run(db, ws.id, PhaseKey.PROJECTS.value)
    if projects_phase.status == PhaseStatus.LOCKED.value:
        projects_phase.status = PhaseStatus.ACTIVE.value
        projects_phase.progress_pct = 10

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="outreach.agreement",
        entity_id=str(company_id),
    )
    db.commit()
    db.refresh(agr)
    return {
        "id": agr.id,
        "company_id": company_id,
        "company_name": company.name,
        "summary": agr.summary,
        "status": agr.status,
    }


def mark_opened(db: Session, comm_id: int, *, actor_email: str) -> dict:
    comm = db.query(Communication).filter(Communication.id == comm_id).one()
    comm.opened_at = datetime.now(timezone.utc)
    comm.delivery_status = "opened"
    company = db.query(Company).filter(Company.id == comm.company_id).one()
    db.commit()
    return _comm_out(comm, company)
