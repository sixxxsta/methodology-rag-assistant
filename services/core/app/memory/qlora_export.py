from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Communication, CommunicationOutcome, Company
from ..services import ensure_workspace

logger = logging.getLogger(__name__)


def _build_instruction(company: Company | None, comm: Communication) -> str:
    parts = [
        f"Напиши партнёрское письмо для программы проектного обучения УрФУ.",
        f"Тон: {comm.tone}. Тип: {comm.comm_type}.",
    ]
    if company:
        parts.append(f"Компания: {company.name}. Отрасль: {company.industry or 'IT'}.")
        if company.description:
            parts.append(f"Описание: {company.description[:800]}")
    return "\n".join(parts)


def export_training_jsonl(db: Session, *, output_dir: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    ws = ensure_workspace(db)
    out_dir = output_dir or Path(settings.qlora_dataset_dir)
    if not out_dir.is_absolute():
        out_dir = Path(__file__).resolve().parents[2] / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "comms_success.jsonl"

    rows = (
        db.query(CommunicationOutcome)
        .filter(
            CommunicationOutcome.workspace_id == ws.id,
            CommunicationOutcome.outcome == "success",
            CommunicationOutcome.communication_id.isnot(None),
        )
        .order_by(CommunicationOutcome.created_at.desc())
        .all()
    )

    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for outcome in rows:
            comm = (
                db.query(Communication)
                .filter(Communication.id == outcome.communication_id)
                .one_or_none()
            )
            if not comm or not (comm.body or "").strip():
                continue
            company = (
                db.query(Company).filter(Company.id == outcome.company_id).one_or_none()
            )
            record = {
                "instruction": _build_instruction(company, comm),
                "input": "",
                "output": f"Тема: {comm.subject}\n\n{comm.body}",
                "metadata": {
                    "outcome_id": outcome.id,
                    "company_id": outcome.company_id,
                    "tone": comm.tone,
                    "comm_type": comm.comm_type,
                },
            }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1

    meta_path = out_dir / "dataset_meta.json"
    meta = {
        "workspace_id": ws.id,
        "records": written,
        "source_outcomes": len(rows),
        "path": str(out_path),
        "base_model_hint": settings.qlora_base_model,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported %d QLoRA samples to %s", written, out_path)
    return meta
