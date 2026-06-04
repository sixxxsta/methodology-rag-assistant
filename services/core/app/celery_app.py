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
    "expire-catalog-projects": {
        "task": "app.tasks.expire_catalog_projects",
        "schedule": float(settings.catalog_expire_interval_seconds),
    },
    "remind-catalog-expiring": {
        "task": "app.tasks.remind_catalog_expiring",
        "schedule": float(settings.catalog_reminder_interval_seconds),
    },
}
