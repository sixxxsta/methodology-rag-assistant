from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

HH_API = "https://api.hh.ru"


def search_employers(
    *,
    user_agent: str,
    text: str,
    area_id: str | None = None,
    per_page: int = 20,
    max_pages: int = 5,
    access_token: str = "",
) -> list[dict[str, Any]]:
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    results: list[dict[str, Any]] = []
    page = 0

    with httpx.Client(timeout=30.0, headers=headers) as client:
        while page < max_pages:
            params: dict[str, Any] = {"text": text, "per_page": min(per_page, 100), "page": page}
            if area_id:
                params["area"] = area_id

            resp = client.get(f"{HH_API}/employers", params=params)
            resp.raise_for_status()
            payload = resp.json()
            items = payload.get("items") or []
            if not items:
                break

            for item in items:
                eid = item.get("id")
                if eid:
                    detail = _fetch_employer(client, str(eid))
                    results.append(detail or item)
                else:
                    results.append(item)

            page += 1
            if page >= payload.get("pages", page + 1):
                break

    logger.info("HH employers: %d for query=%r", len(results), text)
    return results


def _fetch_employer(client: httpx.Client, employer_id: str) -> dict[str, Any] | None:
    try:
        resp = client.get(f"{HH_API}/employers/{employer_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.warning("employer %s: %s", employer_id, exc)
        return None


def employer_to_company_fields(emp: dict[str, Any], default_industry: str) -> dict[str, Any]:
    area = emp.get("area") or {}
    site = emp.get("site_url") or emp.get("alternate_url") or ""
    industries = emp.get("industries") or []
    ind_name = industries[0].get("name") if industries else default_industry

    description_parts = [emp.get("description") or "", emp.get("branded_description") or ""]
    description = "\n".join(p for p in description_parts if p)[:4000]

    open_vac = emp.get("open_vacancies") or 0
    size = "medium"
    if open_vac and open_vac > 50:
        size = "large"
    elif open_vac and open_vac < 5:
        size = "small"

    return {
        "external_id": str(emp.get("id", "")),
        "name": (emp.get("name") or "Без названия")[:512],
        "industry": (ind_name or default_industry)[:255] if ind_name else default_industry,
        "region": (area.get("name") or "")[:255] or None,
        "website": site[:512] if site else None,
        "description": description or None,
        "employee_count": open_vac if isinstance(open_vac, int) else None,
        "size_category": size,
        "has_education_program": "образован" in description.lower()
        or "студент" in description.lower()
        or "стажиров" in description.lower(),
        "source": "hh",
    }
