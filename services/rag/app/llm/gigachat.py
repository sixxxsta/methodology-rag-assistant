from __future__ import annotations

import logging
import time
import uuid

import httpx

from .base import LLMProvider

logger = logging.getLogger(__name__)

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"


class GigaChatLLM(LLMProvider):
    def __init__(
        self,
        credentials: str,
        *,
        scope: str = "GIGACHAT_API_PERS",
        model: str = "GigaChat",
        verify_ssl: bool = False,
        timeout_seconds: int = 120,
    ):
        if not credentials.strip():
            raise ValueError("GIGACHAT_CREDENTIALS is required for gigachat provider")
        self._credentials = credentials.strip()
        self._scope = scope
        self._model = model
        self._verify_ssl = verify_ssl
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token

        headers = {
            "Authorization": f"Basic {self._credentials}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        resp = await client.post(
            OAUTH_URL,
            headers=headers,
            data={"scope": self._scope},
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("GigaChat OAuth returned no access_token")

        expires_in = int(data.get("expires_at", 0)) or int(data.get("expires_in", 1800))
        if expires_in > 10_000_000_000:
            self._token_expires_at = expires_in / 1000.0
        else:
            self._token_expires_at = now + float(expires_in)

        self._token = token
        logger.info("GigaChat token refreshed")
        return token

    async def generate(
        self,
        message: str,
        *,
        context: str = "",
        language: str | None = None,
    ) -> str:
        system_parts = []
        if context:
            system_parts.append(context)
        if language and language != "auto":
            system_parts.append(f"Отвечай на языке: {language}.")

        messages: list[dict[str, str]] = []
        if system_parts:
            messages.append({"role": "system", "content": "\n\n".join(system_parts)})
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=self._timeout, verify=self._verify_ssl) as client:
            token = await self._get_token(client)
            resp = await client.post(
                CHAT_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 1024,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("GigaChat returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        response = (content or "").strip()
        if not response:
            raise RuntimeError("GigaChat returned empty response")
        return response
