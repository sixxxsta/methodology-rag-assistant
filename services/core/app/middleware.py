from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .cycles.context import (
    get_request_cycle_id,
    reset_request_cycle_id,
    reset_request_user,
    set_request_cycle_id,
    set_request_user,
)
from .security import normalize_role

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = cid

        cycle_token = None
        user_token = None
        raw_cycle = request.headers.get("X-Cycle-Id", "").strip()
        if raw_cycle.isdigit():
            cycle_token = set_request_cycle_id(int(raw_cycle))

        email = (request.headers.get("X-User-Email") or "").strip().lower()
        role = normalize_role(request.headers.get("X-User-Role") or "")
        if email:
            user_token = set_request_user(
                {
                    "email": email,
                    "role": role,
                    "user_id": (request.headers.get("X-User-Id") or "").strip(),
                }
            )

        try:
            response = await call_next(request)
            response.headers["X-Correlation-Id"] = cid
            return response
        finally:
            if cycle_token is not None:
                reset_request_cycle_id(cycle_token)
            if user_token is not None:
                reset_request_user(user_token)
