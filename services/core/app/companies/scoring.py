from __future__ import annotations

import json
from dataclasses import dataclass

from ..competency.skills import extract_skills
from ..models import Company, Competency


@dataclass
class ScoreResult:
    total: int
    breakdown: dict[str, int]


def _size_score(company: Company) -> int:
    if company.size_category == "large":
        return 20
    if company.size_category == "medium":
        return 16
    if company.size_category == "small":
        return 10
    if company.employee_count:
        if company.employee_count >= 1000:
            return 18
        if company.employee_count >= 100:
            return 14
        return 8
    return 5


def score_company(company: Company, industry_skills: set[str]) -> ScoreResult:
    text = " ".join(
        filter(
            None,
            [company.description or "", company.tech_stack or "", company.name],
        )
    )
    company_skills = set(extract_skills(text))
    if industry_skills:
        overlap = len(company_skills & industry_skills)
        competency_pts = min(40, int(overlap / max(len(industry_skills), 1) * 40) + overlap * 2)
    else:
        competency_pts = min(40, len(company_skills) * 4)

    size_pts = _size_score(company)
    education_pts = 20 if company.has_education_program else 0
    website_pts = 10 if company.website else 0
    region_pts = 10 if company.region else 5

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
