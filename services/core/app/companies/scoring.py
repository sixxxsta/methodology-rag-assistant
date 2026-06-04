from __future__ import annotations

import json
from dataclasses import dataclass

from ..competency.skills import extract_skills
from ..models import Company, Competency


@dataclass
class ScoreResult:
    total: int
    breakdown: dict[str, int]


def _weights() -> dict[str, int]:
    from .scoring_config import get_runtime_weights

    return get_runtime_weights()


def get_scoring_weights_public() -> dict[str, int]:
    return dict(_weights())


def update_scoring_weights(weights: dict[str, int]) -> dict[str, int]:
    from .scoring_config import set_runtime_weights

    return set_runtime_weights(weights)


def _size_score(company: Company, cap: int) -> int:
    raw = 0
    if company.size_category == "large":
        raw = 20
    elif company.size_category == "medium":
        raw = 16
    elif company.size_category == "small":
        raw = 10
    elif company.employee_count:
        if company.employee_count >= 1000:
            raw = 18
        elif company.employee_count >= 100:
            raw = 14
        else:
            raw = 8
    else:
        raw = 5
    return min(cap, int(raw * cap / 20)) if cap < 20 else raw


def score_company(company: Company, industry_skills: set[str]) -> ScoreResult:
    w = _weights()
    text = " ".join(
        filter(
            None,
            [company.description or "", company.tech_stack or "", company.name],
        )
    )
    company_skills = set(extract_skills(text))
    cap_c = w["competency"]
    if industry_skills:
        overlap = len(company_skills & industry_skills)
        competency_pts = min(
            cap_c,
            int(overlap / max(len(industry_skills), 1) * cap_c) + overlap * 2,
        )
    else:
        competency_pts = min(cap_c, len(company_skills) * 4)

    size_pts = _size_score(company, w["size"])
    education_pts = w["education"] if company.has_education_program else 0
    website_pts = w["website"] if company.website else max(0, w["website"] // 2)
    region_pts = w["region"] if company.region else max(0, w["region"] // 2)

    total = min(100, competency_pts + size_pts + education_pts + website_pts + region_pts)
    breakdown = {
        "competency_match": competency_pts,
        "size": size_pts,
        "education_experience": education_pts,
        "website": website_pts,
        "region": region_pts,
    }
    return ScoreResult(total=total, breakdown=breakdown)


def industry_skill_set(competencies: list[Competency]) -> set[str]:
    skills: set[str] = set()
    for c in competencies:
        if c.source == "industry" and (c.demand_score or 0) > 0:
            skills.add(c.name)
    if not skills:
        for c in competencies:
            if c.source == "program":
                skills.add(c.name)
    return skills


def apply_score(company: Company, result: ScoreResult) -> None:
    company.score = result.total
    company.score_breakdown = json.dumps(result.breakdown, ensure_ascii=False)
