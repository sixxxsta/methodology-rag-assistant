from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (
    PHASE_ORDER,
    Company,
    Competency,
    PartnershipCycle,
    PhaseKey,
    PhaseRun,
    PhaseStatus,
    Project,
    Vacancy,
    Workspace,
)
from .context import get_request_cycle_id


@dataclass
class WorkContext:
    workspace: Workspace
    cycle: PartnershipCycle

    @property
    def workspace_id(self) -> int:
        return self.workspace.id

    @property
    def cycle_id(self) -> int:
        return self.cycle.id


def ensure_workspace(db: Session) -> Workspace:
    ws = db.query(Workspace).order_by(Workspace.id).first()
    if ws:
        return ws
    ws = Workspace(name="ПроКомпетенции — партнёрство")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def _init_phase_runs(db: Session, cycle_id: int) -> None:
    for i, key in enumerate(PHASE_ORDER):
        status = PhaseStatus.ACTIVE.value if i == 0 else PhaseStatus.LOCKED.value
        db.add(
            PhaseRun(
                cycle_id=cycle_id,
                phase_key=key.value,
                status=status,
                progress_pct=5 if i == 0 else 0,
            )
        )


def ensure_phase_runs(db: Session, cycle_id: int) -> None:
    existing = {
        row.phase_key
        for row in db.query(PhaseRun).filter(PhaseRun.cycle_id == cycle_id).all()
    }
    added = False
    for i, key in enumerate(PHASE_ORDER):
        if key.value in existing:
            continue
        status = PhaseStatus.ACTIVE.value if i == 0 and not existing else PhaseStatus.LOCKED.value
        db.add(
            PhaseRun(
                cycle_id=cycle_id,
                phase_key=key.value,
                status=status,
                progress_pct=5 if status == PhaseStatus.ACTIVE.value else 0,
            )
        )
        added = True
    if added:
        db.commit()


def get_phase_run(db: Session, cycle_id: int, phase_key: str) -> PhaseRun:
    ensure_phase_runs(db, cycle_id)
    run = (
        db.query(PhaseRun)
        .filter(PhaseRun.cycle_id == cycle_id, PhaseRun.phase_key == phase_key)
        .one_or_none()
    )
    if not run:
        raise ValueError(f"phase not found: {phase_key}")
    return run


def _active_cycle_query(db: Session, workspace_id: int):
    return (
        db.query(PartnershipCycle)
        .filter(
            PartnershipCycle.workspace_id == workspace_id,
            PartnershipCycle.status == "active",
        )
        .order_by(PartnershipCycle.id.desc())
    )


def ensure_default_cycle(db: Session, ws: Workspace) -> PartnershipCycle:
    cycle = _active_cycle_query(db, ws.id).first()
    if cycle:
        ensure_phase_runs(db, cycle.id)
        return cycle

    any_cycle = (
        db.query(PartnershipCycle)
        .filter(PartnershipCycle.workspace_id == ws.id)
        .order_by(PartnershipCycle.id)
        .first()
    )
    if any_cycle:
        any_cycle.status = "active"
        ensure_phase_runs(db, any_cycle.id)
        db.commit()
        return any_cycle

    return create_cycle(db, name="Цикл 1", actor_email="system", activate=True)


def get_work_context(db: Session, cycle_id: int | None = None) -> WorkContext:
    ws = ensure_workspace(db)
    requested = cycle_id if cycle_id is not None else get_request_cycle_id()
    if requested is not None:
        cycle = (
            db.query(PartnershipCycle)
            .filter(
                PartnershipCycle.id == requested,
                PartnershipCycle.workspace_id == ws.id,
            )
            .one_or_none()
        )
        if not cycle:
            raise ValueError("cycle not found")
        ensure_phase_runs(db, cycle.id)
        return WorkContext(workspace=ws, cycle=cycle)

    cycle = ensure_default_cycle(db, ws)
    return WorkContext(workspace=ws, cycle=cycle)


def _cycle_dict(cycle: PartnershipCycle, *, project_count: int = 0, company_count: int = 0) -> dict:
    return {
        "id": cycle.id,
        "workspace_id": cycle.workspace_id,
        "name": cycle.name,
        "industry": cycle.industry,
        "status": cycle.status,
        "created_by": cycle.created_by,
        "created_at": cycle.created_at.isoformat() if cycle.created_at else None,
        "project_count": project_count,
        "company_count": company_count,
        "is_active": cycle.status == "active",
    }


def list_cycles(db: Session) -> list[dict]:
    ws = ensure_workspace(db)
    rows = (
        db.query(PartnershipCycle)
        .filter(PartnershipCycle.workspace_id == ws.id)
        .order_by(PartnershipCycle.id.desc())
        .all()
    )
    out: list[dict] = []
    for cycle in rows:
        pc = db.query(Project).filter(Project.cycle_id == cycle.id).count()
        cc = db.query(Company).filter(Company.cycle_id == cycle.id).count()
        out.append(_cycle_dict(cycle, project_count=pc, company_count=cc))
    return out


def create_cycle(
    db: Session,
    *,
    name: str | None = None,
    actor_email: str,
    activate: bool = True,
) -> dict:
    ws = ensure_workspace(db)
    count = db.query(PartnershipCycle).filter(PartnershipCycle.workspace_id == ws.id).count()
    label = (name or "").strip() or f"Цикл {count + 1}"

    if activate:
        db.query(PartnershipCycle).filter(PartnershipCycle.workspace_id == ws.id).update(
            {"status": "archived"},
            synchronize_session=False,
        )

    cycle = PartnershipCycle(
        workspace_id=ws.id,
        name=label,
        status="active" if activate else "archived",
        created_by=actor_email,
    )
    db.add(cycle)
    db.flush()
    _init_phase_runs(db, cycle.id)

    from ..competency.service import seed_program_competencies

    seed_program_competencies(db, ws.id, cycle_id=cycle.id)

    db.commit()
    db.refresh(cycle)
    return _cycle_dict(cycle)


def set_active_cycle(db: Session, cycle_id: int, *, actor_email: str) -> dict:
    ws = ensure_workspace(db)
    cycle = (
        db.query(PartnershipCycle)
        .filter(PartnershipCycle.id == cycle_id, PartnershipCycle.workspace_id == ws.id)
        .one_or_none()
    )
    if not cycle:
        raise ValueError("cycle not found")

    db.query(PartnershipCycle).filter(PartnershipCycle.workspace_id == ws.id).update(
        {"status": "archived"},
        synchronize_session=False,
    )
    cycle.status = "active"
    db.commit()
    db.refresh(cycle)
    return _cycle_dict(cycle)


def reopen_phase(db: Session, cycle_id: int, phase_key: str, *, actor_email: str) -> dict:
    ws = ensure_workspace(db)
    cycle = (
        db.query(PartnershipCycle)
        .filter(PartnershipCycle.id == cycle_id, PartnershipCycle.workspace_id == ws.id)
        .one_or_none()
    )
    if not cycle:
        raise ValueError("cycle not found")

    run = get_phase_run(db, cycle.id, phase_key)
    run.status = PhaseStatus.ACTIVE.value
    if run.progress_pct <= 0:
        run.progress_pct = 5

    from ..services import log_action

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="cycle.phase_reopen",
        entity_type="phase",
        entity_id=phase_key,
        details=f"cycle_id={cycle_id}",
    )
    db.commit()
    db.refresh(run)

    from ..services import _phase_out

    return _phase_out(run).model_dump()


def unlock_next_phase(db: Session, cycle_id: int, completed_key: PhaseKey) -> None:
    idx = PHASE_ORDER.index(completed_key)
    if idx + 1 >= len(PHASE_ORDER):
        return
    next_key = PHASE_ORDER[idx + 1]
    nxt = get_phase_run(db, cycle_id, next_key.value)
    if nxt.status == PhaseStatus.LOCKED.value:
        nxt.status = PhaseStatus.ACTIVE.value
        db.commit()


def migrate_legacy_workspace_to_cycles(db: Session) -> None:
    """One-time: attach existing rows without cycle_id to a default cycle."""
    ws = ensure_workspace(db)
    if db.query(PartnershipCycle).filter(PartnershipCycle.workspace_id == ws.id).first():
        return

    cycle = PartnershipCycle(
        workspace_id=ws.id,
        name="Цикл 1 (архив данных)",
        industry=ws.industry,
        status="active",
        created_by="migration",
    )
    db.add(cycle)
    db.flush()
    _init_phase_runs(db, cycle.id)

    for model, col in (
        (Company, Company.cycle_id),
        (Competency, Competency.cycle_id),
        (Vacancy, Vacancy.cycle_id),
        (Project, Project.cycle_id),
    ):
        db.query(model).filter(
            model.workspace_id == ws.id,
            col.is_(None),
        ).update({col.key: cycle.id}, synchronize_session=False)

    old_phases = (
        db.query(PhaseRun)
        .filter(PhaseRun.cycle_id == cycle.id)
        .all()
    )
    if len(old_phases) == len(PHASE_ORDER):
        pass

    db.commit()
