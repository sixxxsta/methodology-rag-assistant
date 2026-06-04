from __future__ import annotations

from celery import Celery

from .config import get_settings

settings = get_settings()

celery_app = Celery("edagent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    "process-due-followups": {
        "task": "app.tasks.process_due_followups",
        "schedule": float(settings.celery_followup_interval_seconds),
    },
    "poll-imap-inbox": {
        "task": "app.tasks.poll_imap_inbox",
        "schedule": float(settings.imap_poll_interval_seconds),
    },
    "process-email-outbox": {
        "task": "app.tasks.process_email_outbox",
        "schedule": float(settings.email_outbox_interval_seconds),
    },
}
