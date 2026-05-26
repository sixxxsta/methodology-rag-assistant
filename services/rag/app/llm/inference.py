from __future__ import annotations

import httpx

from .base import LLMProvider


class InferenceLLM(LLMProvider):
    def __init__(self, base_url: str, timeout_seconds: int):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def generate(
        self,
        message: str,
        *,
        context: str = "",
        language: str | None = None,
    ) -> str:
        payload: dict[str, str | None] = {
            "message": message,
            "context": context,
            "language": language,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base_url}/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        response = (data.get("response") or "").strip()
        if not response:
            raise RuntimeError("inference server returned empty response")
        return response
