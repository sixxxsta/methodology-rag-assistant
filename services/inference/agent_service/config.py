from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _find_root_env() -> Path | None:
    start = Path(__file__).resolve()
    for parent in [start, *start.parents]:
        if (parent / "docker-compose.yml").exists() and (parent / ".env").exists():
            return parent / ".env"
        if parent == parent.parent:
            break
    cwd_env = Path.cwd() / ".env"
    return cwd_env if cwd_env.exists() else None


def _load_env_file() -> None:
    env_path = _find_root_env()
    if env_path:
        load_dotenv(env_path, override=False)


def _to_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model_name: str
    use_4bit: bool
    min_new_tokens: int
    max_new_tokens: int
    temperature: float
    top_p: float
    repetition_penalty: float
    context_max_chars: int
    response_language: str
    system_prompt: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_env_file()

    return Settings(
        model_name=os.getenv("MODEL_NAME", "Qwen/Qwen2.5-3B-Instruct"),
        use_4bit=_to_bool(os.getenv("USE_4BIT"), True),
        min_new_tokens=int(os.getenv("MIN_NEW_TOKENS", "180")),
        max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "700")),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
        top_p=float(os.getenv("TOP_P", "0.9")),
        repetition_penalty=float(os.getenv("REPETITION_PENALTY", "1.05")),
        context_max_chars=int(os.getenv("CONTEXT_MAX_CHARS", "4000")),
        response_language=os.getenv("RESPONSE_LANGUAGE", "auto"),
        system_prompt=os.getenv(
            "SYSTEM_PROMPT",
            "Ты — методологический ментор для студенческих проектных команд.",
        ),
    )
