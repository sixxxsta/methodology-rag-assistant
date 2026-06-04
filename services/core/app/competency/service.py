from __future__ import annotations

import csv
import io
import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Competency, PhaseKey, Vacancy
from ..cycles.service import get_work_context
from ..services import log_action, update_phase
from .providers import get_vacancy_provider
from .providers.base import vacancy_body
from .skills import aggregate_skill_counts_weighted

logger = logging.getLogger(__name__)

PROGRAM_DATA = Path(__file__).resolve().parents[2] / "data" / "program_competencies.json"


def seed_program_competencies(db: Session, workspace_id: int, *, cycle_id: int) -> int:
    if not PROGRAM_DATA.exists():
        logger.warning("program competencies file missing: %s", PROGRAM_DATA)
        return 0

    existing = (
        db.query(Competency)
        .filter(
            Competency.workspace_id == workspace_id,
            Competency.cycle_id == cycle_id,
            Competency.source == "program",
        )
        .count()
    )
    if existing > 0:
        return existing

    items = json.loads(PROGRAM_DATA.read_text(encoding="utf-8"))
    added = 0
    for item in items:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        db.add(
            Competency(
                workspace_id=workspace_id,
                cycle_id=cycle_id,
                name=name,
                source="program",
                program_level=int(item.get("level", 3)),
            )
        )
        added += 1
    db.commit()
    return added


def collect_vacancies(
    db: Session,
    *,
    actor_email: str,
    query: str,
    area_id: str | None = None,
    max_pages: int = 2,
    provider: str = "hh",
) -> dict:
    settings = get_settings()
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    seed_program_competencies(db, ws.id, cycle_id=cid)

    prov = get_vacancy_provider(provider, settings)
    vacancies = prov.search_vacancies(
        text=query,
        area_id=area_id,
        max_pages=max_pages,
    )
    demo_mode = getattr(prov, "demo_mode", False)
    provider_message = getattr(prov, "message", None)
    source = prov.name

    processed: list[dict] = []
    stored = 0
    for v in vacancies:
        ext_id = str(v.get("id", ""))
        if ext_id:
            exists = (
                db.query(Vacancy)
                .filter(Vacancy.cycle_id == cid, Vacancy.external_id == ext_id)
                .first()
            )
            if exists:
                processed.append(v)
                continue

        body = vacancy_body(v)
        processed.append(v)
        db.add(
            Vacancy(
                workspace_id=ws.id,
                cycle_id=cid,
                external_id=ext_id or None,
                title=(v.get("name") or "Без названия")[:512],
                source=source,
                raw_text=body[:8000] if body else None,
            )
        )
        stored += 1

    skill_counts = aggregate_skill_counts_weighted(processed)

    db.query(Competency).filter(
        Competency.cycle_id == cid,
        Competency.source == "industry",
    ).delete()

    for name, demand in skill_counts.items():
        db.add(
            Competency(
                workspace_id=ws.id,
                cycle_id=cid,
                name=name,
                source="industry",
                demand_score=demand,
            )
        )

    progress = min(90, 20 + len(processed) * 2)
    update_phase(
        db,
        PhaseKey.INDUSTRY.value,
        actor_email=actor_email,
        progress_pct=progress,
        notes=f"[{source}] вакансий: {len(processed)}, навыков: {len(skill_counts)}",
    )

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="competency.collect",
        entity_type=source,
        details=f"provider={source}, query={query}, vacancies={len(processed)}, skills={len(skill_counts)}",
    )
    db.commit()

    matrix = build_matrix(db)
    if matrix["summary"]["gaps"] >= 5:
        from ..models import Escalation, EscalationStatus
        from ..services import create_escalation

        open_esc = (
            db.query(Escalation)
            .filter(
                Escalation.cycle_id == cid,
                Escalation.level == 1,
                Escalation.status == EscalationStatus.OPEN.value,
            )
            .first()
        )
        if not open_esc:
            create_escalation(
                db,
                workspace_id=ws.id,
                cycle_id=cid,
                phase_key=PhaseKey.INDUSTRY.value,
                level=1,
                title="Сильное отставание программы от рынка",
                description=(
                    f"Выявлено {matrix['summary']['gaps']} пробелов. "
                    "Утвердите отрасль и приоритеты на дашборде."
                ),
            )
            db.commit()

    return {
        "vacancies_collected": len(processed),
        "vacancies_new": stored,
        "skills_found": len(skill_counts),
        "query": query,
        "provider": source,
        "demo_mode": demo_mode,
        "message": provider_message,
    }


def collect_from_hh(
    db: Session,
    *,
    actor_email: str,
    query: str,
    area_id: str | None = None,
    max_pages: int = 2,
) -> dict:
    return collect_vacancies(
        db,
        actor_email=actor_email,
        query=query,
        area_id=area_id,
        max_pages=max_pages,
        provider="hh",
    )


def export_matrix_csv(db: Session) -> str:
    data = build_matrix(db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "skill",
            "program_level",
            "industry_demand_pct",
            "industry_level_est",
            "gap_type",
        ]
    )
    for item in data["items"]:
        writer.writerow(
            [
                item["name"],
                item["program_level"],
                item["industry_demand_pct"],
                item["industry_level_est"],
                item["gap_type"],
            ]
        )
    return buf.getvalue()


def build_matrix(db: Session) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    seed_program_competencies(db, ws.id, cycle_id=cid)

    program = {
        c.name: c.program_level or 0
        for c in db.query(Competency)
        .filter(Competency.cycle_id == cid, Competency.source == "program")
        .all()
    }
    industry = {
        c.name: c.demand_score or 0
        for c in db.query(Competency)
        .filter(Competency.cycle_id == cid, Competency.source == "industry")
        .all()
    }

    all_names = sorted(set(program) | set(industry))
    items: list[dict] = []
    gaps = aligned = excess = 0

    for name in all_names:
        prog = program.get(name, 0)
        ind = industry.get(name, 0)
        ind_level = max(1, min(5, round(ind / 20))) if ind else 0

        if prog == 0 and ind > 0:
            gap_type = "missing_in_program"
            gaps += 1
        elif prog > 0 and ind == 0:
            gap_type = "niche_program"
            excess += 1
        elif prog > 0 and ind > 0:
            diff = ind_level - prog
            if diff >= 2:
                gap_type = "undertrained"
                gaps += 1
            elif diff <= -2:
                gap_type = "overtrained"
                excess += 1
            else:
                gap_type = "aligned"
                aligned += 1
        else:
            gap_type = "unknown"
            continue

        items.append(
            {
                "name": name,
                "program_level": prog,
                "industry_demand_pct": ind,
                "industry_level_est": ind_level,
                "gap_type": gap_type,
            }
        )

    items.sort(key=lambda x: (-x["industry_demand_pct"], x["name"]))

    vacancy_count = (
        db.query(Vacancy).filter(Vacancy.cycle_id == cid).count()
    )

    return {
        "workspace_id": ws.id,
        "industry": ws.industry,
        "vacancy_count": vacancy_count,
        "summary": {
            "total": len(items),
            "gaps": gaps,
            "aligned": aligned,
            "excess": excess,
        },
        "items": items,
    }


def matrix_chart(db: Session) -> dict:
    data = build_matrix(db)
    by_gap: dict[str, int] = {}
    for item in data["items"]:
        gap_type = item["gap_type"]
        by_gap[gap_type] = by_gap.get(gap_type, 0) + 1

    top_gaps = sorted(
        [i for i in data["items"] if i["gap_type"] not in ("aligned", "unknown")],
        key=lambda x: (-x["industry_demand_pct"], x["name"]),
    )[:12]

    comparison = sorted(data["items"], key=lambda x: (-x["industry_demand_pct"], x["name"]))[:15]

    return {
        "workspace_id": data["workspace_id"],
        "industry": data["industry"],
        "vacancy_count": data["vacancy_count"],
        "summary": data["summary"],
        "by_gap_type": [
            {"gap_type": gap_type, "count": count}
            for gap_type, count in sorted(by_gap.items(), key=lambda x: -x[1])
        ],
        "top_gaps": top_gaps,
        "comparison": [
            {
                "name": item["name"],
                "program_level": item["program_level"],
                "industry_level_est": item["industry_level_est"],
                "industry_demand_pct": item["industry_demand_pct"],
                "gap_type": item["gap_type"],
            }
            for item in comparison
        ],
    }


def get_stats(db: Session) -> dict:
    ctx = get_work_context(db)
    ws = ctx.workspace
    cid = ctx.cycle_id
    return {
        "program_competencies": db.query(Competency)
        .filter(Competency.cycle_id == cid, Competency.source == "program")
        .count(),
        "industry_competencies": db.query(Competency)
        .filter(Competency.cycle_id == cid, Competency.source == "industry")
        .count(),
        "vacancies": db.query(Vacancy).filter(Vacancy.cycle_id == cid).count(),
    }
