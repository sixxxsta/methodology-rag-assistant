from __future__ import annotations

from ..config import get_settings

_override: dict[str, int] | None = None


def _defaults() -> dict[str, int]:
    s = get_settings()
    return {
        "competency": s.score_weight_competency,
        "size": s.score_weight_size,
        "education": s.score_weight_education,
        "website": s.score_weight_website,
        "region": s.score_weight_region,
    }


def get_runtime_weights() -> dict[str, int]:
    if _override is not None:
        return dict(_override)
    return _defaults()


def set_runtime_weights(weights: dict[str, int]) -> dict[str, int]:
    global _override
    keys = ("competency", "size", "education", "website", "region")
    merged = _defaults()
    for key in keys:
        if key in weights:
            val = int(weights[key])
            if val < 0 or val > 100:
                raise ValueError(f"weight {key} must be 0..100")
            merged[key] = val
    total = sum(merged.values())
    if total != 100:
        raise ValueError(f"weights must sum to 100, got {total}")
    _override = merged
    return dict(merged)
