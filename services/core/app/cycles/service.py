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
from .context import get_request_cycle_id, get_request_user


DELETED_STATUS = "deleted"


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


def _norm_email(email: str | None) -> str:
    return (email or "").strip().lower()



def _is_admin(user: dict[str, str]) -> bool:
    return user.get("role") == "admin"


def _cycles_query(db: Session, workspace_id: int, user: dict[str, str] | None = None):
    q = db.query(PartnershipCycle).filter(
        PartnershipCycle.workspace_id == workspace_id,
        PartnershipCycle.status != DELETED_STATUS,
    )
    if user and not _is_admin(user):
        email = _norm_email(user["email"])
        q = q.filter(PartnershipCycle.created_by == email)
    return q


def _get_cycle_or_raise(
    db: Session,
    workspace_id: int,
    cycle_id: int,
    user: dict[str, str] | None = None,
) -> PartnershipCycle:
    cycle = (
        _cycles_query(db, workspace_id, user)
        .filter(PartnershipCycle.id == cycle_id)
        .one_or_none()
    )
    if not cycle:
        raise ValueError("cycle not found")
    return cycle


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


def _active_cycle_for_user(db: Session, ws: Workspace, user: dict[str, str]) -> PartnershipCycle | None:
    return (
        _cycles_query(db, ws.id, user)
        .filter(PartnershipCycle.status == "active")
        .order_by(PartnershipCycle.id.desc())
        .first()
    )


def ensure_default_cycle(db: Session, ws: Workspace, user: dict[str, str]) -> PartnershipCycle:
    cycle = _active_cycle_for_user(db, ws, user)
    if cycle:
        ensure_phase_runs(db, cycle.id)
        return cycle

    any_cycle = _cycles_query(db, ws.id, user).order_by(PartnershipCycle.id.desc()).first()
    if any_cycle:
        any_cycle.status = "active"
        ensure_phase_runs(db, any_cycle.id)
        db.commit()
        return any_cycle

    return create_cycle(
        db,
        name="Цикл 1",
        actor_email=user["email"],
        activate=True,
    )


def get_work_context(db: Session, cycle_id: int | None = None) -> WorkContext:
    user = get_request_user()
    ws = ensure_workspace(db)
    requested = cycle_id if cycle_id is not None else get_request_cycle_id()

    if user and user.get("email"):
        if requested is not None:
            cycle = _get_cycle_or_raise(db, ws.id, requested, user)
            ensure_phase_runs(db, cycle.id)
            return WorkContext(workspace=ws, cycle=cycle)
        cycle = ensure_default_cycle(db, ws, user)
        return WorkContext(workspace=ws, cycle=cycle)

    if requested is not None:
        cycle = (
            db.query(PartnershipCycle)
            .filter(
                PartnershipCycle.workspace_id == ws.id,
                PartnershipCycle.id == requested,
                PartnershipCycle.status != DELETED_STATUS,
            )
            .one_or_none()
        )
        if not cycle:
            raise ValueError("cycle not found")
        ensure_phase_runs(db, cycle.id)
        return WorkContext(workspace=ws, cycle=cycle)

    cycle = (
        db.query(PartnershipCycle)
        .filter(
            PartnershipCycle.workspace_id == ws.id,
            PartnershipCycle.status == "active",
        )
        .order_by(PartnershipCycle.id.desc())
        .first()
    )
    if not cycle:
        cycle = (
            db.query(PartnershipCycle)
            .filter(
                PartnershipCycle.workspace_id == ws.id,
                PartnershipCycle.status != DELETED_STATUS,
            )
            .order_by(PartnershipCycle.id.desc())
            .first()
        )
    if not cycle:
        raise ValueError("no partnership cycle")
    ensure_phase_runs(db, cycle.id)
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
        "is_owner": True,
    }


def list_cycles(db: Session, *, actor_email: str, actor_role: str) -> list[dict]:
    user = {"email": actor_email, "role": actor_role}
    ws = ensure_workspace(db)
    rows = _cycles_query(db, ws.id, user).order_by(PartnershipCycle.id.desc()).all()
    email = _norm_email(actor_email)
    out: list[dict] = []
    for cycle in rows:
        pc = db.query(Project).filter(Project.cycle_id == cycle.id).count()
        cc = db.query(Company).filter(Company.cycle_id == cycle.id).count()
        item = _cycle_dict(cycle, project_count=pc, company_count=cc)
        item["is_owner"] = _is_admin(user) or _norm_email(cycle.created_by) == email
        out.append(item)
    return out


def create_cycle(
    db: Session,
    *,
    name: str | None = None,
    actor_email: str,
    actor_role: str = "curator",
    activate: bool = True,
) -> PartnershipCycle:
    user = {"email": actor_email, "role": actor_role}
    ws = ensure_workspace(db)
    email = _norm_email(actor_email)
    count = _cycles_query(db, ws.id, user).count()
    label = (name or "").strip() or f"Цикл {count + 1}"

    if activate:
        for row in _cycles_query(db, ws.id, user).filter(PartnershipCycle.status == "active").all():
            row.status = "archived"

    cycle = PartnershipCycle(
        workspace_id=ws.id,
        name=label,
        status="active" if activate else "archived",
        created_by=email,
    )
    db.add(cycle)
    db.flush()
    _init_phase_runs(db, cycle.id)

    from ..competency.service import seed_program_competencies

    seed_program_competencies(db, ws.id, cycle_id=cycle.id)

    db.commit()
    db.refresh(cycle)
    return cycle


def set_active_cycle(
    db: Session,
    cycle_id: int,
    *,
    actor_email: str,
    actor_role: str = "curator",
) -> dict:
    user = {"email": actor_email, "role": actor_role}
    ws = ensure_workspace(db)
    cycle = _get_cycle_or_raise(db, ws.id, cycle_id, user)

    for row in _cycles_query(db, ws.id, user).filter(PartnershipCycle.status == "active").all():
        row.status = "archived"
    cycle.status = "active"
    db.commit()
    db.refresh(cycle)
    return _cycle_dict(cycle)


def delete_cycle(
    db: Session,
    cycle_id: int,
    *,
    actor_email: str,
    actor_role: str = "curator",
) -> dict:
    user = {"email": actor_email, "role": actor_role}
    ws = ensure_workspace(db)
    cycle = _get_cycle_or_raise(db, ws.id, cycle_id, user)
    was_active = cycle.status == "active"
    cycle.status = DELETED_STATUS

    from ..services import log_action

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="cycle.delete",
        entity_type="cycle",
        entity_id=str(cycle_id),
    )

    if was_active:
        replacement = (
            _cycles_query(db, ws.id, user)
            .filter(PartnershipCycle.id != cycle_id)
            .order_by(PartnershipCycle.id.desc())
            .first()
        )
        if replacement:
            replacement.status = "active"

    db.commit()
    return {"status": "deleted", "cycle_id": cycle_id}


def reopen_phase(
    db: Session,
    cycle_id: int,
    phase_key: str,
    *,
    actor_email: str,
    actor_role: str = "curator",
) -> dict:
    user = {"email": actor_email, "role": actor_role}
    ws = ensure_workspace(db)
    cycle = _get_cycle_or_raise(db, ws.id, cycle_id, user)

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

    db.commit()
