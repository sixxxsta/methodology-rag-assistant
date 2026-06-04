from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = cid
        return response
