from __future__ import annotations

from .celery_app import celery_app
from .database import SessionLocal
from .outreach.imap_poller import poll_imap_inbox
from .outreach.service import process_due_followups_auto


@celery_app.task(name="app.tasks.process_due_followups")
def process_due_followups() -> dict:
    db = SessionLocal()
    try:
        return process_due_followups_auto(db)
    finally:
        db.close()


@celery_app.task(name="app.tasks.discover_companies", bind=True)
def discover_companies(
    self,
    actor_email: str,
    query: str | None = None,
    max_pages: int = 3,
) -> dict:
    from .companies.service import discover_employers

    db = SessionLocal()
    try:
        result = discover_employers(
            db,
            actor_email=actor_email,
            query=query,
            max_pages=max_pages,
        )
        return result
    finally:
        db.close()


@celery_app.task(name="app.tasks.poll_imap_inbox")
def poll_imap() -> dict:
    db = SessionLocal()
    try:
        return poll_imap_inbox(db)
    finally:
        db.close()


@celery_app.task(name="app.tasks.process_email_outbox")
def process_email_outbox() -> dict:
    from .outreach.outbox import process_outbox_batch

    db = SessionLocal()
    try:
        return process_outbox_batch(db)
    finally:
        db.close()
