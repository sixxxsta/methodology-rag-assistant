from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://edagent:edagent@postgres:5432/edagent"
    core_internal_secret: str = ""
    cors_origins: str = "*"
    hh_user_agent: str = "EdAgent/1.0 (contact@urfu.ru)"
    hh_access_token: str = ""
    hh_default_area_id: str = "1"
    hh_cache_ttl_seconds: int = 3600
    hh_request_delay_ms: int = 200
    rag_service_url: str = "http://rag:8100"
    rag_timeout_seconds: int = 120
    program_name: str = "ПроКомпетенции"
    comms_use_llm: bool = False
    comms_llm_timeout_seconds: int = 20
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    redis_url: str = "redis://redis:6379/0"
    celery_followup_interval_seconds: int = 3600
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    notify_email: str = ""
    outreach_tracking_base_url: str = ""
    email_webhook_secret: str = ""
    outreach_use_llm: bool = True
    superjob_app_id: str = ""
    superjob_secret_key: str = ""
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_use_ssl: bool = True
    imap_poll_interval_seconds: int = 300
    strategy_memory_enabled: bool = True
    qlora_dataset_dir: str = "data/qlora"
    qlora_base_model: str = "IlyaGusev/saiga_llama3_8b"
    score_weight_competency: int = 40
    score_weight_size: int = 20
    score_weight_education: int = 20
    score_weight_website: int = 10
    score_weight_region: int = 10
    email_queue_enabled: bool = False
    email_queue_max_attempts: int = 3
    email_outbox_interval_seconds: int = 60
    catalog_expire_interval_seconds: int = 3600
    catalog_expiry_reminder_days_before: int = 7
    catalog_reminder_interval_seconds: int = 86400


@lru_cache
def get_settings() -> Settings:
    return Settings()
