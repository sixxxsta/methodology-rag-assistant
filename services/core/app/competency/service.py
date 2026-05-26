from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import get_settings
from ..hh_fallback import (
    hh_error_hint,
    is_hh_user_agent_rejected,
    load_demo_vacancies,
)
from ..models import Competency, PhaseKey, Vacancy
from ..services import ensure_workspace, log_action, update_phase
from .hh_client import HeadHunterClient
from .skills import aggregate_skill_counts

logger = logging.getLogger(__name__)

PROGRAM_DATA = Path(__file__).resolve().parents[2] / "data" / "program_competencies.json"


def seed_program_competencies(db: Session, workspace_id: int) -> int:
    if not PROGRAM_DATA.exists():
        logger.warning("program competencies file missing: %s", PROGRAM_DATA)
        return 0

    existing = (
        db.query(Competency)
        .filter(Competency.workspace_id == workspace_id, Competency.source == "program")
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
                name=name,
                source="program",
                program_level=int(item.get("level", 3)),
            )
        )
        added += 1
    db.commit()
    return added


def collect_from_hh(
    db: Session,
    *,
    actor_email: str,
    query: str,
    area_id: str | None = None,
    max_pages: int = 2,
) -> dict:
    settings = get_settings()
    ws = ensure_workspace(db)
    seed_program_competencies(db, ws.id)

    demo_mode = False
    hh_message: str | None = None
    vacancies: list[dict] = []

    if is_hh_user_agent_rejected(settings.hh_user_agent):
        demo_mode = True
        hh_message = (
            "В HH_USER_AGENT указан example.com — API hh.ru блокирует такой контакт. "
            "Используются демо-вакансии."
        )
        vacancies = load_demo_vacancies(query)
    else:
        client = HeadHunterClient(
            user_agent=settings.hh_user_agent,
            access_token=settings.hh_access_token,
        )
        try:
            vacancies = client.search_vacancies(
                text=query,
                area_id=area_id or settings.hh_default_area_id or None,
                max_pages=max_pages,
            )
        except Exception as exc:
            logger.warning("HH collect failed, demo fallback: %s", exc)
            demo_mode = True
            hh_message = hh_error_hint(exc)
            vacancies = load_demo_vacancies(query)

    texts: list[str] = []
    stored = 0
    for v in vacancies:
        ext_id = str(v.get("id", ""))
        if ext_id:
            exists = (
                db.query(Vacancy)
                .filter(Vacancy.workspace_id == ws.id, Vacancy.external_id == ext_id)
                .first()
            )
            if exists:
                texts.append(HeadHunterClient.vacancy_text(v))
                continue

        body = HeadHunterClient.vacancy_text(v)
        texts.append(body)
        db.add(
            Vacancy(
                workspace_id=ws.id,
                external_id=ext_id or None,
                title=(v.get("name") or "Без названия")[:512],
                source="hh",
                raw_text=body[:8000] if body else None,
            )
        )
        stored += 1

    skill_counts = aggregate_skill_counts(texts)
    total_vacancies = max(len(texts), 1)

    db.query(Competency).filter(
        Competency.workspace_id == ws.id,
        Competency.source == "industry",
    ).delete()

    for name, count in skill_counts.items():
        demand = min(100, int(round(count / total_vacancies * 100)))
        db.add(
            Competency(
                workspace_id=ws.id,
                name=name,
                source="industry",
                demand_score=demand,
            )
        )

    progress = min(90, 20 + len(texts) * 2)
    update_phase(
        db,
        PhaseKey.INDUSTRY.value,
        actor_email=actor_email,
        progress_pct=progress,
        notes=f"Собрано вакансий: {len(texts)}, навыков: {len(skill_counts)}",
    )

    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="competency.collect",
        entity_type="hh",
        details=f"query={query}, vacancies={len(texts)}, skills={len(skill_counts)}",
    )
    db.commit()

    matrix = build_matrix(db)
    if matrix["summary"]["gaps"] >= 5:
        from ..models import Escalation, EscalationStatus
        from ..services import create_escalation

        open_esc = (
            db.query(Escalation)
            .filter(
                Escalation.workspace_id == ws.id,
                Escalation.level == 1,
                Escalation.status == EscalationStatus.OPEN.value,
            )
            .first()
        )
        if not open_esc:
            create_escalation(
                db,
                workspace_id=ws.id,
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
        "vacancies_collected": len(texts),
        "vacancies_new": stored,
        "skills_found": len(skill_counts),
        "query": query,
        "demo_mode": demo_mode,
        "message": hh_message,
    }


def build_matrix(db: Session) -> dict:
    ws = ensure_workspace(db)
    seed_program_competencies(db, ws.id)

    program = {
        c.name: c.program_level or 0
        for c in db.query(Competency)
        .filter(Competency.workspace_id == ws.id, Competency.source == "program")
        .all()
    }
    industry = {
        c.name: c.demand_score or 0
        for c in db.query(Competency)
        .filter(Competency.workspace_id == ws.id, Competency.source == "industry")
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
        db.query(Vacancy).filter(Vacancy.workspace_id == ws.id).count()
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


def get_stats(db: Session) -> dict:
    ws = ensure_workspace(db)
    return {
        "program_competencies": db.query(Competency)
        .filter(Competency.workspace_id == ws.id, Competency.source == "program")
        .count(),
        "industry_competencies": db.query(Competency)
        .filter(Competency.workspace_id == ws.id, Competency.source == "industry")
        .count(),
        "vacancies": db.query(Vacancy).filter(Vacancy.workspace_id == ws.id).count(),
    }
