from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Communication, CommunicationVersion


def snapshot_version(
    db: Session,
    comm: Communication,
    *,
    edited_by: str | None = None,
) -> CommunicationVersion:
    row = CommunicationVersion(
        communication_id=comm.id,
        version=comm.version,
        subject=comm.subject,
        body=comm.body,
        value_proposition=comm.value_proposition,
        edited_by=edited_by,
    )
    db.add(row)
    return row


def list_versions(db: Session, comm_id: int) -> list[dict]:
    rows = (
        db.query(CommunicationVersion)
        .filter(CommunicationVersion.communication_id == comm_id)
        .order_by(CommunicationVersion.version.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "version": r.version,
            "subject": r.subject,
            "body": r.body,
            "value_proposition": r.value_proposition,
            "edited_by": r.edited_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
