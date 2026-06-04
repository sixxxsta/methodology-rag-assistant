from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from ..competency.skills import extract_skills, normalize_skill_label

logger = logging.getLogger(__name__)

_META_DESC = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_META_KEYWORDS = re.compile(
    r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_TITLE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def _normalize_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValueError("empty website url")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.netloc:
        raise ValueError("invalid website url")
    return raw


def fetch_website_profile(url: str, *, timeout: float = 12.0) -> dict[str, Any]:
    target = _normalize_url(url)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(
            target,
            headers={"User-Agent": "EdAgent/1.0 (company enrichment bot)"},
        )
        resp.raise_for_status()
        html = resp.text[:200_000]

    title_match = _TITLE.search(html)
    title = title_match.group(1).strip() if title_match else ""

    desc_match = _META_DESC.search(html)
    description = desc_match.group(1).strip() if desc_match else ""

    keywords: list[str] = []
    kw_match = _META_KEYWORDS.search(html)
    if kw_match:
        keywords = [k.strip() for k in kw_match.group(1).split(",") if k.strip()]

    plain = _TAG_RE.sub(" ", html)
    plain = re.sub(r"\s+", " ", plain)[:8000]
    if not description:
        description = plain[:500]

    skills = set(extract_skills(plain))
    for kw in keywords[:20]:
        label = normalize_skill_label(kw)
        if label:
            skills.add(label)

    return {
        "url": target,
        "title": title[:512],
        "description": description[:4000],
        "keywords": keywords[:30],
        "tech_stack": ", ".join(sorted(skills)[:25]),
        "skills_found": sorted(skills),
    }
