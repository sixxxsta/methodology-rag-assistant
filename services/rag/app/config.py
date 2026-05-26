from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_root_env() -> Path | None:
    start = Path(__file__).resolve()
    for parent in [start, *start.parents]:
        compose = parent / "docker-compose.yml"
        env_file = parent / ".env"
        if compose.exists() and env_file.exists():
            return env_file
        if parent == parent.parent:
            break
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if candidate.exists():
            return candidate
    return None


def _load_env() -> None:
    env_path = _find_root_env()
    if env_path:
        load_dotenv(env_path, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "methodology_kb"
    qdrant_api_key: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_batch_size: int = 32
    rag_top_k: int = 5
    rag_score_threshold: float = 0.45
    chunk_size: int = 800
    chunk_overlap: int = 120
    knowledge_dir: str = "/knowledge"
    llm_provider: str = "auto"
    inference_base_url: str = "http://127.0.0.1:8000"
    inference_timeout_seconds: int = 600
    gigachat_credentials: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_verify_ssl: bool = False
    system_prompt: str = Field(default="Ты — методологический ментор.")
    response_language: str = "auto"
    rag_http_port: int = 8100
    auto_ingest_on_startup: bool = True
    cors_origins: str = "*"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env()
    return Settings(
        qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "methodology_kb"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        ),
        embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
        rag_top_k=int(os.getenv("RAG_TOP_K", "5")),
        rag_score_threshold=float(os.getenv("RAG_SCORE_THRESHOLD", "0.45")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "800")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "120")),
        knowledge_dir=os.getenv("KNOWLEDGE_DIR", "/knowledge"),
        llm_provider=os.getenv("LLM_PROVIDER", "auto").strip().lower(),
        inference_base_url=os.getenv("INFERENCE_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        inference_timeout_seconds=int(os.getenv("INFERENCE_TIMEOUT_SECONDS", "600")),
        gigachat_credentials=os.getenv("GIGACHAT_CREDENTIALS", ""),
        gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        gigachat_model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        gigachat_verify_ssl=os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() in {"1", "true", "yes"},
        system_prompt=os.getenv(
            "SYSTEM_PROMPT",
            "Ты — методологический ментор для студенческих проектных команд.",
        ),
        response_language=os.getenv("RESPONSE_LANGUAGE", "auto"),
        rag_http_port=int(os.getenv("RAG_HTTP_PORT", "8100")),
        auto_ingest_on_startup=os.getenv("AUTO_INGEST_ON_STARTUP", "true").lower() in {"1", "true", "yes"},
        cors_origins=os.getenv("CORS_ORIGINS", "*"),
    )
