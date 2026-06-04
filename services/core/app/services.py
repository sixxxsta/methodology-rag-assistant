from __future__ import annotations

from sqlalchemy.orm import Session

from .cycles.service import (
    ensure_phase_runs,
    ensure_workspace,
    get_phase_run,
    get_work_context,
    unlock_next_phase,
)
from .models import (
    PHASE_META,
    PHASE_ORDER,
    AuditLog,
    Escalation,
    EscalationStatus,
    PhaseKey,
    PhaseRun,
    PhaseStatus,
)
from .schemas import (
    AuditLogOut,
    CycleOut,
    DashboardOut,
    EscalationOut,
    PhaseOut,
    WorkspaceOut,
)


def _phase_out(run: PhaseRun) -> PhaseOut:
    key = PhaseKey(run.phase_key)
    meta = PHASE_META[key]
    return PhaseOut(
        key=run.phase_key,
        title=meta["title"],
        description=meta["description"],
        status=run.status,
        progress_pct=run.progress_pct,
        order=PHASE_ORDER.index(key) + 1,
        notes=run.notes,
        updated_at=run.updated_at,
    )


def get_dashboard(db: Session) -> DashboardOut:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cycle = ctx.cycle
    phases = (
        db.query(PhaseRun)
        .filter(PhaseRun.cycle_id == cycle.id)
        .order_by(PhaseRun.id)
        .all()
    )
    open_count = (
        db.query(Escalation)
        .filter(
            Escalation.cycle_id == cycle.id,
            Escalation.status == EscalationStatus.OPEN.value,
        )
        .count()
    )
    escalations = (
        db.query(Escalation)
        .filter(Escalation.cycle_id == cycle.id)
        .order_by(Escalation.created_at.desc())
        .limit(20)
        .all()
    )
    audit = (
        db.query(AuditLog)
        .filter(AuditLog.workspace_id == ws.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )

    workspace_out = WorkspaceOut(
        id=ws.id,
        name=ws.name,
        industry=cycle.industry or ws.industry,
        created_at=ws.created_at,
        phases=[_phase_out(p) for p in phases],
        open_escalations=open_count,
        active_cycle=CycleOut(
            id=cycle.id,
            name=cycle.name,
            industry=cycle.industry,
            status=cycle.status,
            is_active=cycle.status == "active",
        ),
    )
    return DashboardOut(
        workspace=workspace_out,
        escalations=[EscalationOut.model_validate(e) for e in escalations],
        recent_audit=[AuditLogOut.model_validate(a) for a in audit],
    )


def log_action(
    db: Session,
    *,
    workspace_id: int | None,
    actor_email: str,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: str | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        )
    )


def update_phase(
    db: Session,
    phase_key: str,
    *,
    actor_email: str,
    status: str | None = None,
    progress_pct: int | None = None,
    notes: str | None = None,
) -> PhaseOut:
    ctx = get_work_context(db)
    run = get_phase_run(db, ctx.cycle_id, phase_key)
    if status is not None:
        run.status = status
    if progress_pct is not None:
        run.progress_pct = progress_pct
    if notes is not None:
        run.notes = notes

    log_action(
        db,
        workspace_id=ctx.workspace_id,
        actor_email=actor_email,
        action="phase.update",
        entity_type="phase",
        entity_id=phase_key,
        details=f"cycle={ctx.cycle_id}, status={run.status}, progress={run.progress_pct}",
    )
    db.commit()
    db.refresh(run)
    return _phase_out(run)


def create_escalation(
    db: Session,
    *,
    workspace_id: int,
    cycle_id: int,
    phase_key: str,
    level: int,
    title: str,
    description: str,
) -> Escalation:
    esc = Escalation(
        workspace_id=workspace_id,
        cycle_id=cycle_id,
        phase_key=phase_key,
        level=level,
        title=title,
        description=description,
    )
    db.add(esc)
    db.flush()
    try:
        from .notifications import notify_escalation

        notify_escalation(level=level, title=title, description=description)
    except Exception:
        pass
    return esc


def resolve_escalation(
    db: Session,
    escalation_id: int,
    *,
    actor_email: str,
    status: str,
    comment: str | None,
) -> EscalationOut:
    from datetime import datetime, timezone

    esc = db.query(Escalation).filter(Escalation.id == escalation_id).one()
    esc.status = status
    esc.resolved_by = actor_email
    esc.resolved_at = datetime.now(timezone.utc)

    log_action(
        db,
        workspace_id=esc.workspace_id,
        actor_email=actor_email,
        action="escalation.resolve",
        entity_type="escalation",
        entity_id=str(escalation_id),
        details=comment or status,
    )
    db.commit()
    db.refresh(esc)
    return EscalationOut.model_validate(esc)


def approve_industry(
    db: Session,
    *,
    actor_email: str,
    industry: str,
    comment: str | None,
) -> DashboardOut:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cycle = ctx.cycle
    industry_text = industry.strip()
    cycle.industry = industry_text
    ws.industry = industry_text

    industry_phase = get_phase_run(db, ctx.cycle_id, PhaseKey.INDUSTRY.value)
    industry_phase.status = PhaseStatus.COMPLETED.value
    industry_phase.progress_pct = 100

    unlock_next_phase(db, ctx.cycle_id, PhaseKey.INDUSTRY)

    open_esc = (
        db.query(Escalation)
        .filter(
            Escalation.cycle_id == cycle.id,
            Escalation.level == 1,
            Escalation.status == EscalationStatus.OPEN.value,
        )
        .all()
    )
    from datetime import datetime, timezone

    for esc in open_esc:
        esc.status = EscalationStatus.RESOLVED.value
        esc.resolved_by = actor_email
        esc.resolved_at = datetime.now(timezone.utc)

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="industry.approve",
        entity_type="cycle",
        entity_id=str(cycle.id),
        details=f"industry={industry}; {comment or ''}".strip(),
    )
    db.commit()
    return get_dashboard(db)


def seed_escalation_if_needed(db: Session) -> None:
    ctx = get_work_context(db)
    industry = get_phase_run(db, ctx.cycle_id, PhaseKey.INDUSTRY.value)
    if industry.status != PhaseStatus.ACTIVE.value:
        return
    exists = (
        db.query(Escalation)
        .filter(Escalation.cycle_id == ctx.cycle_id, Escalation.level == 1)
        .first()
    )
    if exists:
        return
    create_escalation(
        db,
        workspace_id=ctx.workspace_id,
        cycle_id=ctx.cycle_id,
        phase_key=PhaseKey.INDUSTRY.value,
        level=1,
        title="Утвердите отрасль и приоритеты",
        description="Агент завершил черновой анализ. Подтвердите отрасль для поиска партнёров.",
    )
    db.commit()
