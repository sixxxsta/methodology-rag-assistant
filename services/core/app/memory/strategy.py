from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import Communication, CommunicationOutcome, StrategyPattern
from ..services import ensure_workspace, log_action

logger = logging.getLogger(__name__)

MAX_PATTERN_LEN = 2500
MAX_HINTS = 3


def _pattern_from_communication(comm: Communication) -> str:
    parts = [f"Тема: {comm.subject}", comm.body or ""]
    if comm.value_proposition:
        parts.append(f"Ценностное предложение:\n{comm.value_proposition}")
    return "\n\n".join(p for p in parts if p).strip()[:MAX_PATTERN_LEN]


def ingest_from_outcome(db: Session, outcome_row: CommunicationOutcome) -> StrategyPattern | None:
    if outcome_row.outcome not in ("success", "fail"):
        return None

    category = "letter"
    tone: str | None = None
    pattern_text = outcome_row.notes or ""

    if outcome_row.communication_id:
        comm = (
            db.query(Communication)
            .filter(Communication.id == outcome_row.communication_id)
            .one_or_none()
        )
        if comm:
            category = comm.comm_type or "letter"
            tone = comm.tone
            pattern_text = _pattern_from_communication(comm)

    if not pattern_text.strip():
        try:
            feats = json.loads(outcome_row.features_json or "{}")
        except json.JSONDecodeError:
            feats = {}
        pattern_text = json.dumps(feats, ensure_ascii=False)[:MAX_PATTERN_LEN]

    if not pattern_text.strip():
        return None

    existing = (
        db.query(StrategyPattern)
        .filter(
            StrategyPattern.workspace_id == outcome_row.workspace_id,
            StrategyPattern.source_outcome_id == outcome_row.id,
        )
        .first()
    )
    if existing:
        _bump_counts(existing, outcome_row.outcome)
        existing.pattern_text = pattern_text
        db.flush()
        return existing

    row = StrategyPattern(
        workspace_id=outcome_row.workspace_id,
        category=category,
        tone=tone,
        outcome=outcome_row.outcome,
        pattern_text=pattern_text,
        source_outcome_id=outcome_row.id,
        source_communication_id=outcome_row.communication_id,
        success_count=1 if outcome_row.outcome == "success" else 0,
        fail_count=1 if outcome_row.outcome == "fail" else 0,
        score=1.0 if outcome_row.outcome == "success" else -0.5,
    )
    db.add(row)
    db.flush()
    return row


def _bump_counts(pattern: StrategyPattern, outcome: str) -> None:
    if outcome == "success":
        pattern.success_count += 1
        pattern.score = pattern.success_count / max(1, pattern.success_count + pattern.fail_count)
    else:
        pattern.fail_count += 1
        pattern.score = pattern.success_count / max(1, pattern.success_count + pattern.fail_count) - 0.2


def sync_all_from_outcomes(db: Session, *, actor_email: str) -> dict:
    ws = ensure_workspace(db)
    rows = (
        db.query(CommunicationOutcome)
        .filter(CommunicationOutcome.workspace_id == ws.id)
        .order_by(CommunicationOutcome.created_at.desc())
        .all()
    )
    ingested = 0
    for row in rows:
        if ingest_from_outcome(db, row):
            ingested += 1
    log_action(
        db,
        workspace_id=ws.id,
        actor_email=actor_email,
        action="memory.sync",
        details=f"patterns={ingested}",
    )
    db.commit()
    return {"outcomes_scanned": len(rows), "patterns_upserted": ingested}


def list_patterns(
    db: Session,
    *,
    category: str | None = None,
    tone: str | None = None,
    outcome: str | None = None,
    limit: int = 20,
) -> list[dict]:
    ws = ensure_workspace(db)
    q = db.query(StrategyPattern).filter(StrategyPattern.workspace_id == ws.id)
    if category:
        q = q.filter(StrategyPattern.category == category)
    if tone:
        q = q.filter(StrategyPattern.tone == tone)
    if outcome:
        q = q.filter(StrategyPattern.outcome == outcome)
    rows = q.order_by(StrategyPattern.score.desc(), StrategyPattern.updated_at.desc()).limit(limit).all()
    return [_pattern_dict(p) for p in rows]


def get_strategy_hints(
    db: Session,
    *,
    category: str = "letter",
    tone: str | None = "formal",
) -> str:
    ws = ensure_workspace(db)
    rows = (
        db.query(StrategyPattern)
        .filter(
            StrategyPattern.workspace_id == ws.id,
            StrategyPattern.category == category,
            StrategyPattern.outcome == "success",
        )
        .order_by(StrategyPattern.score.desc(), StrategyPattern.success_count.desc())
        .limit(MAX_HINTS * 2)
        .all()
    )
    if tone:
        preferred = [r for r in rows if r.tone == tone]
        others = [r for r in rows if r.tone != tone]
        rows = (preferred + others)[:MAX_HINTS]
    else:
        rows = rows[:MAX_HINTS]

    if not rows:
        return ""

    blocks: list[str] = []
    for i, row in enumerate(rows, start=1):
        excerpt = row.pattern_text[:800]
        blocks.append(
            f"Пример {i} (успех, score={row.score:.2f}, tone={row.tone or '—'}):\n{excerpt}"
        )
    return (
        "Учитывай успешные паттерны из прошлых кампаний (не копируй дословно):\n"
        + "\n---\n".join(blocks)
    )


def memory_stats(db: Session) -> dict:
    ws = ensure_workspace(db)
    total = (
        db.query(StrategyPattern)
        .filter(StrategyPattern.workspace_id == ws.id)
        .count()
    )
    success = (
        db.query(StrategyPattern)
        .filter(StrategyPattern.workspace_id == ws.id, StrategyPattern.outcome == "success")
        .count()
    )
    outcomes = (
        db.query(CommunicationOutcome)
        .filter(CommunicationOutcome.workspace_id == ws.id)
        .count()
    )
    return {
        "patterns_total": total,
        "patterns_success": success,
        "outcomes_total": outcomes,
        "strategy_memory_enabled": True,
    }


def _pattern_dict(p: StrategyPattern) -> dict:
    return {
        "id": p.id,
        "category": p.category,
        "tone": p.tone,
        "outcome": p.outcome,
        "pattern_text": p.pattern_text[:500] + ("…" if len(p.pattern_text) > 500 else ""),
        "success_count": p.success_count,
        "fail_count": p.fail_count,
        "score": round(p.score, 3),
        "source_outcome_id": p.source_outcome_id,
        "source_communication_id": p.source_communication_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
