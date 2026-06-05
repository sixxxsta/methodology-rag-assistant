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
    ProjectEnrollment,
    StudentProfile,
    TouchPoint,
)
from ..cycles.service import get_work_context, get_phase_run, unlock_next_phase
from ..services import (
    create_escalation,
    log_action,
    update_phase,
)
from ..config import get_settings
from .classifier import auto_reply_for, classify_response
from .mailer import send_email, smtp_configured
from .outcomes import record_outcome
from .tracking import new_tracking_token, tracking_pixel_url

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
        "tracking_token": comm.tracking_token,
        "sent_at": comm.sent_at.isoformat() if comm.sent_at else None,
        "delivered_at": comm.delivered_at.isoformat() if comm.delivered_at else None,
        "opened_at": comm.opened_at.isoformat() if comm.opened_at else None,
    }


def dashboard(db: Session) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    approved = (
        db.query(Communication)
        .join(Company, Communication.company_id == Company.id)
        .filter(
            Company.cycle_id == cid,
            Communication.status == "approved",
            Communication.comm_type == "letter",
        )
        .all()
    )
    sent = sum(1 for c in approved if c.delivery_status in ("sent", "delivered", "opened"))
    delivered = sum(1 for c in approved if c.delivery_status in ("delivered", "opened"))
    opened = sum(1 for c in approved if c.delivery_status == "opened")
    pending = len(approved) - sent

    responses = (
        db.query(Interaction)
        .join(Company, Interaction.company_id == Company.id)
        .filter(Company.cycle_id == cid, Interaction.direction == "inbound")
        .order_by(Interaction.created_at.desc())
        .limit(50)
        .all()
    )

    due_followups = _due_touchpoints(db, ws.id)

    companies = (
        db.query(Company)
        .filter(
            Company.cycle_id == cid,
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
        "letters_delivered": delivered,
        "letters_opened": opened,
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


def _interaction_dict_extended(db: Session, i: Interaction, **extra) -> dict:
    base = _interaction_dict(db, i)
    base.update(extra)
    return base


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
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id

    if not comm.tracking_token:
        comm.tracking_token = new_tracking_token()

    settings = get_settings()
    pixel_url = None
    if settings.outreach_tracking_base_url:
        pixel_url = tracking_pixel_url(comm.tracking_token, settings.outreach_tracking_base_url)

    if use_smtp and smtp_configured():
        if not company.contact_email:
            raise ValueError("company has no contact email")
        if settings.email_queue_enabled:
            from .outbox import enqueue_email

            enqueue_email(
                db,
                communication_id=comm.id,
                to_email=company.contact_email,
                subject=comm.subject,
                body=comm.body,
                tracking_token=comm.tracking_token,
            )
            comm.delivery_status = "queued"
        else:
            send_email(
                to=company.contact_email,
                subject=comm.subject,
                body=comm.body,
                tracking_pixel_url=pixel_url,
            )
            comm.delivery_status = "sent"
    else:
        comm.delivery_status = "sent_manual"

    now = datetime.now(timezone.utc)
    if comm.delivery_status != "queued":
        comm.sent_at = now
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
            Company.cycle_id == cid,
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
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    settings = get_settings()

    prompt = f"""Напиши короткое follow-up письмо (напоминание) для {company.name}.
Контекст: ранее отправляли приглашение к партнёрству с УрФУ, ответа не было.
Тон вежливый, 5-8 предложений, call-to-action — короткий созвон."""
    if settings.strategy_memory_enabled:
        from ..memory.strategy import get_strategy_hints

        hints = get_strategy_hints(db, category="followup", tone="formal")
        if hints:
            prompt = f"{hints}\n\n---\n\n{prompt}"

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


def process_due_followups_auto(db: Session) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    due = _due_touchpoints(db, ws.id)
    sent: list[int] = []
    errors: list[str] = []
    for item in due:
        try:
            send_followup(db, item["touch_id"], actor_email="system@edagent")
            sent.append(item["touch_id"])
        except Exception as exc:
            errors.append(f"{item['touch_id']}: {exc}")
    return {"due": len(due), "sent": len(sent), "errors": errors}


def record_inbound(
    db: Session,
    company_id: int,
    *,
    actor_email: str,
    subject: str,
    body: str,
    auto_respond: bool = True,
) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    company = (
        db.query(Company)
        .filter(Company.cycle_id == cid, Company.id == company_id)
        .one_or_none()
    )
    if not company:
        raise ValueError(
            f"компания с id={company_id} не найдена. Выберите компанию из списка на странице «Компании»."
        )
    classification_result = classify_response(subject, body)
    classification = classification_result.category
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
    db.flush()

    if classification in ("interest", "meeting_request"):
        _escalation_4(db, ws.id, cid, company.name, classification)

    if classification == "reject":
        record_outcome(
            db,
            workspace_id=ws.id,
            cycle_id=cid,
            company_id=company.id,
            outcome="fail",
            actor_email=actor_email,
            interaction_id=interaction.id,
            features={
                "classification": classification,
                "classification_confidence": classification_result.confidence,
                "classification_method": classification_result.method,
            },
        )

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
        **_interaction_dict_extended(
            db,
            interaction,
            classification_confidence=classification_result.confidence,
            classification_method=classification_result.method,
        ),
        "auto_reply": auto_reply,
        "needs_human": classification in ("interest", "meeting_request"),
    }


def _escalation_4(db: Session, workspace_id: int, cycle_id: int, company_name: str, kind: str) -> None:
    if (
        db.query(Escalation)
        .filter(
            Escalation.cycle_id == cycle_id,
            Escalation.level == 4,
            Escalation.status == EscalationStatus.OPEN.value,
        )
        .first()
    ):
        return
    create_escalation(
        db,
        workspace_id=workspace_id,
        cycle_id=cycle_id,
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
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    company = (
        db.query(Company)
        .filter(Company.cycle_id == cid, Company.id == company_id)
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

    last_comm = (
        db.query(Communication)
        .filter(
            Communication.company_id == company.id,
            Communication.comm_type.in_(("letter", "followup")),
        )
        .order_by(Communication.sent_at.desc().nullslast(), Communication.created_at.desc())
        .first()
    )

    record_outcome(
        db,
        workspace_id=ws.id,
        cycle_id=cid,
        company_id=company.id,
        outcome="success",
        actor_email=actor_email,
        communication_id=last_comm.id if last_comm else None,
        features={"agreement_status": status, "summary_len": len(summary)},
        notes=summary[:500],
    )

    phase = get_phase_run(db, cid, PhaseKey.OUTREACH.value)
    if phase.status == PhaseStatus.ACTIVE.value:
        phase.progress_pct = 100
        phase.status = PhaseStatus.COMPLETED.value
        unlock_next_phase(db, cid, PhaseKey.OUTREACH)

    projects_phase = get_phase_run(db, cid, PhaseKey.PROJECTS.value)
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
