from fastapi import Header, HTTPException

from .config import get_settings


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

    return {
        "email": email,
        "user_id": (x_user_id or "").strip(),
        "role": (x_user_role or "user").strip(),
    }
