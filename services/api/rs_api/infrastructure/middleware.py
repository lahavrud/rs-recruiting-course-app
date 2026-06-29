"""FastAPI middleware: request correlation IDs and APM latency logging.

The framework-free logging primitives (`request_id_var`, `RequestIdFilter`)
live in `request_context.py` so the worker can use them without Starlette;
they're re-exported here for backward compatibility with existing imports.
"""

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
from opentelemetry import trace as otel_trace
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from rs_shared.core.infrastructure.request_context import (
    RequestIdFilter,
    request_id_var,
)

__all__ = ["RequestIdFilter", "RequestMiddleware", "request_id_var"]

logger = logging.getLogger(__name__)

_HEALTH_PATH = "/health"


class RequestMiddleware(BaseHTTPMiddleware):
    """Per-request correlation ID + APM latency in a single middleware pass.

    Generates a UUID per request, stores it in a ContextVar so every log line
    in the request carries the same request_id, and returns it as X-Request-ID.

    Logs method/path/status_code/duration_ms on every response (including
    errors — the finally block fires even when call_next raises) for p95/p99
    latency analysis in Grafana (logs ship via OTLP → Loki).

    /health is excluded from APM logging (Route 53 polls it every 30 s).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        span = otel_trace.get_current_span()
        span_context = span.get_span_context()
        if span_context.is_valid:
            span.set_attribute("app.request_id", rid)
            sentry_sdk.set_tag("trace_id", format(span_context.trace_id, "032x"))

        path = request.url.path
        t0 = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            if path != _HEALTH_PATH:
                duration_ms = round((time.perf_counter() - t0) * 1000)
                logger.info(
                    "request",
                    extra={
                        "request_id": rid,
                        "method": request.method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    },
                )
