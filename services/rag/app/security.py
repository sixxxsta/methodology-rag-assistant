from __future__ import annotations

from fastapi import Header, HTTPException

from .config import get_settings


def verify_internal_key(x_rag_internal_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    secret = (settings.rag_internal_secret or "").strip()
    if not secret:
        return
    if not x_rag_internal_key or x_rag_internal_key.strip() != secret:
        raise HTTPException(status_code=403, detail="invalid internal key")
