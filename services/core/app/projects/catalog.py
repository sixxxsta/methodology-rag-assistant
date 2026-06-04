from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import Project

CATALOG_MODE_PERMANENT = "permanent"
CATALOG_MODE_TEMPORARY = "temporary"


def catalog_visible_filter():
    """SQLAlchemy filter: project is shown in student catalog now."""
    now = datetime.now(timezone.utc)
    return (
        Project.catalog_visible.is_(True),
        or_(
            Project.catalog_visible_until.is_(None),
            Project.catalog_visible_until > now,
        ),
    )


def resolve_catalog_until(
    *,
    catalog_mode: str,
    catalog_months: int | None = None,
    catalog_until: datetime | None = None,
) -> datetime | None:
    mode = (catalog_mode or CATALOG_MODE_PERMANENT).strip().lower()
    if mode == CATALOG_MODE_PERMANENT:
        return None
    if catalog_until is not None:
        if catalog_until.tzinfo is None:
            catalog_until = catalog_until.replace(tzinfo=timezone.utc)
        return catalog_until
    months = catalog_months or 5
    if months < 1 or months > 60:
        raise ValueError("catalog_months must be 1..60")
    return datetime.now(timezone.utc) + timedelta(days=30 * months)


def expire_catalog_projects(db: Session) -> dict:
    now = datetime.now(timezone.utc)
    rows = (
        db.query(Project)
        .filter(
            Project.catalog_visible.is_(True),
            Project.catalog_visible_until.isnot(None),
            Project.catalog_visible_until <= now,
        )
        .all()
    )
    for p in rows:
        p.catalog_visible = False
    db.commit()
    return {"expired": len(rows)}


def remind_catalog_expiring_projects(db: Session) -> dict:
    """Notify curator once per project when temporary catalog entry expires soon."""
    from ..config import get_settings
    from ..models import AuditLog, PartnershipCycle
    from ..notifications import notify_catalog_expiring
    from ..services import log_action

    settings = get_settings()
    days_before = settings.catalog_expiry_reminder_days_before
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(days=days_before)

    rows = (
        db.query(Project)
        .filter(
            Project.catalog_visible.is_(True),
            Project.catalog_mode == CATALOG_MODE_TEMPORARY,
            Project.catalog_visible_until.isnot(None),
            Project.catalog_visible_until > now,
            Project.catalog_visible_until <= window_end,
        )
        .all()
    )

    sent = 0
    for project in rows:
        already = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "catalog.expiry.reminder",
                AuditLog.entity_id == str(project.id),
            )
            .count()
        )
        if already:
            continue

        until = project.catalog_visible_until
        days_left = max(0, (until - now).days) if until else 0
        cycle = (
            db.query(PartnershipCycle)
            .filter(PartnershipCycle.id == project.cycle_id)
            .one_or_none()
        )
        curator = cycle.created_by if cycle else None

        notify_catalog_expiring(
            project_title=project.title,
            days_left=days_left,
            until_iso=until.isoformat() if until else "",
            curator_email=curator,
        )
        log_action(
            db,
            workspace_id=project.workspace_id,
            actor_email=curator or "system",
            action="catalog.expiry.reminder",
            entity_type="project",
            entity_id=str(project.id),
            details=f"days_left={days_left}",
        )
        sent += 1

    if sent:
        db.commit()
    return {"reminded": sent, "candidates": len(rows)}


def extend_catalog_visibility(
    db: Session,
    project_id: int,
    *,
    actor_email: str,
    catalog_months: int | None = None,
) -> dict:
    """Extend temporary catalog listing without unpublishing."""
    from ..cycles.service import get_work_context
    from ..services import log_action

    months = catalog_months or 5
    if months < 1 or months > 60:
        raise ValueError("catalog_months must be 1..60")

    ctx = get_work_context(db)
    project = (
        db.query(Project)
        .filter(Project.cycle_id == ctx.cycle_id, Project.id == project_id)
        .one()
    )
    mode = (project.catalog_mode or CATALOG_MODE_PERMANENT).strip().lower()
    if mode != CATALOG_MODE_TEMPORARY:
        raise ValueError("продление доступно только для проектов с ограниченным сроком в каталоге")
    if project.status != "approved":
        raise ValueError("утвердите проект перед продлением каталога")
    if not project.published_at and not project.catalog_visible:
        raise ValueError("сначала опубликуйте проект в каталог")

    now = datetime.now(timezone.utc)
    base = project.catalog_visible_until or now
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if base < now:
        base = now
    new_until = base + timedelta(days=30 * months)

    project.catalog_visible = True
    project.catalog_visible_until = new_until

    log_action(
        db,
        workspace_id=project.workspace_id,
        actor_email=actor_email,
        action="catalog.extend",
        entity_type="project",
        entity_id=str(project.id),
        details=f"months={months};until={new_until.isoformat()}",
    )
    db.commit()
    db.refresh(project)
    return {
        "catalog_visible": project.catalog_visible,
        "catalog_visible_until": new_until.isoformat(),
        "catalog_mode": project.catalog_mode,
        "months_added": months,
    }
