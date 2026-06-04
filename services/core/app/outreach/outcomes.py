from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from ..models import CommunicationOutcome
from ..services import log_action
from ..memory.strategy import ingest_from_outcome

logger = logging.getLogger(__name__)


def record_outcome(
    db: Session,
    *,
    workspace_id: int,
    company_id: int,
    outcome: str,
    actor_email: str,
    communication_id: int | None = None,
    interaction_id: int | None = None,
    features: dict[str, Any] | None = None,
    notes: str | None = None,
) -> dict:
    row = CommunicationOutcome(
        workspace_id=workspace_id,
        company_id=company_id,
        communication_id=communication_id,
        interaction_id=interaction_id,
        outcome=outcome,
        features_json=json.dumps(features or {}, ensure_ascii=False),
        notes=notes,
        recorded_by=actor_email,
    )
    db.add(row)
    log_action(
        db,
        workspace_id=workspace_id,
        actor_email=actor_email,
        action="outreach.outcome",
        entity_id=str(company_id),
        details=outcome,
    )
    db.flush()
    ingest_from_outcome(db, row)
    return {
        "id": row.id,
        "company_id": company_id,
        "outcome": outcome,
        "features": features or {},
    }
