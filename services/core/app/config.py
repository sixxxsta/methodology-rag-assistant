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


@lru_cache
def get_settings() -> Settings:
    return Settings()
