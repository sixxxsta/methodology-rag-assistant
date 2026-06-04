from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_disabled = False
_last_request_at = 0.0


def _redis():
    global _redis_client, _redis_disabled
    if _redis_disabled:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis

        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("Redis cache unavailable: %s", exc)
        _redis_disabled = True
        return None


def _cache_key(url: str, params: dict[str, Any] | None) -> str:
    raw = url
    if params:
        raw += "?" + urlencode(sorted(params.items()))
    digest = hashlib.sha256(raw.encode()).hexdigest()[:32]
    return f"hh:cache:{digest}"


def _throttle() -> None:
    global _last_request_at
    settings = get_settings()
    delay_ms = settings.hh_request_delay_ms
    if delay_ms <= 0:
        return
    now = time.monotonic()
    elapsed_ms = (now - _last_request_at) * 1000
    if elapsed_ms < delay_ms:
        time.sleep((delay_ms - elapsed_ms) / 1000)
    _last_request_at = time.monotonic()


def cached_json_get(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    key = _cache_key(url, params)
    store = _redis()

    if store and settings.hh_cache_ttl_seconds > 0:
        cached = store.get(key)
        if cached:
            logger.debug("HH cache hit: %s", url)
            return json.loads(cached)

    _throttle()
    resp = client.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if store and settings.hh_cache_ttl_seconds > 0:
        store.setex(key, settings.hh_cache_ttl_seconds, json.dumps(data, ensure_ascii=False))

    return data
