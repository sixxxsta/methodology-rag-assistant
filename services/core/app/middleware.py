from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


from .cycles.context import get_request_cycle_id, reset_request_cycle_id, set_request_cycle_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = cid
        cycle_token = None
        raw_cycle = request.headers.get("X-Cycle-Id", "").strip()
        if raw_cycle.isdigit():
            cycle_token = set_request_cycle_id(int(raw_cycle))
        try:
            response = await call_next(request)
            response.headers["X-Correlation-Id"] = cid
            return response
        finally:
            if cycle_token is not None:
                reset_request_cycle_id(cycle_token)
