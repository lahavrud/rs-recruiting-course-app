"""GA4 server-side tunnel — forwards custom events via the Measurement Protocol.

Browser requests to google-analytics.com are blocked by ad blockers and
Firefox Enhanced Tracking Protection. This endpoint acts as a same-origin
relay so conversion events (apply_submit, apply_start, job_view) reach GA4
even when the browser cannot make the cross-origin request itself.

Security:
- Returns 404 when GA4_MEASUREMENT_ID / GA4_API_SECRET are not configured.
- Validates event name format (alphanumeric + underscore, ≤40 chars) to
  prevent the endpoint being used to inject arbitrary event names.
- Rate-limited to 30 req/min per IP.
- GA4 API secret is never echoed in responses or logged.
"""

import logging
import re

import httpx
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from rs_api.infrastructure.limiter import limiter
from rs_shared.core.infrastructure.config import settings

router = APIRouter(tags=["monitoring"])

_logger = logging.getLogger(__name__)

_TUNNEL_RATE = "30/minute"
_GA4_COLLECT_URL = "https://www.google-analytics.com/mp/collect"
_GA4_TIMEOUT = 5.0
_EVENT_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,39}$")


class AnalyticsEvent(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    params: dict[str, str | int | float | bool] = Field(default_factory=dict)
    client_id: str = Field(min_length=1, max_length=256)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not _EVENT_NAME_RE.match(v):
            raise ValueError("invalid event name")
        return v


@router.post("/api/analytics/collect", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(_TUNNEL_RATE)
async def analytics_collect(request: Request, event: AnalyticsEvent) -> Response:
    """Relay a GA4 custom event from the browser to the Measurement Protocol."""
    if not settings.ga4_measurement_id or not settings.ga4_api_secret:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    payload = {
        "client_id": event.client_id,
        "events": [{"name": event.name, "params": event.params}],
    }

    try:
        async with httpx.AsyncClient(timeout=_GA4_TIMEOUT) as client:
            await client.post(
                _GA4_COLLECT_URL,
                params={
                    "measurement_id": settings.ga4_measurement_id,
                    "api_secret": settings.ga4_api_secret,
                },
                json=payload,
            )
    except httpx.RequestError as exc:
        _logger.warning("GA4 tunnel: upstream request failed: %s", exc)

    # Always return 204 — never expose GA4 errors or response body to the browser.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
