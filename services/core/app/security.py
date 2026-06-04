from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from .config import get_settings


def normalize_role(role: str) -> str:
    r = (role or "").strip().lower()
    if r in ("admin", "curator", "student"):
        return r
    if r == "user":
        return "curator"
    return "student"


def require_internal(
    x_core_internal_key: str | None = Header(default=None, alias="X-Core-Internal-Key"),
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> dict[str, str]:
    settings = get_settings()
    if settings.core_internal_secret:
        if x_core_internal_key != settings.core_internal_secret:
            raise HTTPException(status_code=401, detail="invalid internal key")

    email = (x_user_email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=401, detail="user context required")

    role = normalize_role(x_user_role or "student")
    return {
        "email": email,
        "user_id": (x_user_id or "").strip(),
        "role": role,
    }


def _require_edagent(user: dict[str, str]) -> dict[str, str]:
    if user["role"] == "student":
        raise HTTPException(status_code=403, detail="access denied")
    return user


def _require_curator(user: dict[str, str]) -> dict[str, str]:
    if user["role"] not in ("admin", "curator"):
        raise HTTPException(status_code=403, detail="curator required")
    return user


def require_edagent(
    user: Annotated[dict[str, str], Depends(require_internal)],
) -> dict[str, str]:
    return _require_edagent(user)


def require_curator(
    user: Annotated[dict[str, str], Depends(require_internal)],
) -> dict[str, str]:
    return _require_curator(user)


def require_student(
    user: Annotated[dict[str, str], Depends(require_internal)],
) -> dict[str, str]:
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="student required")
    return user
