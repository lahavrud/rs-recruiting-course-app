"""Tests for the Sentry tunnel relay endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient

from rs_shared.core.infrastructure.config import settings

VALID_DSN = "https://abc123@o12345.ingest.sentry.io/4567890"


def _envelope(dsn: str | None) -> bytes:
    header: dict = {"event_id": "deadbeef" * 4, "sent_at": "2026-01-01T00:00:00Z"}
    if dsn is not None:
        header["dsn"] = dsn
    return json.dumps(header).encode() + b'\n{"type":"event","length":2}\n{}\n'


@pytest.fixture
def _configure_dsn(monkeypatch):
    monkeypatch.setattr(settings, "frontend_sentry_dsn", VALID_DSN)


@pytest.mark.asyncio
async def test_returns_404_when_dsn_not_configured(public_client: AsyncClient):
    """If the server has no DSN configured the tunnel returns 404.

    404 (not 5xx) so the backend Sentry SDK doesn't capture it and create
    a feedback loop where the tunnel's own failure gets reported to Sentry.
    """
    # Default settings have empty frontend_sentry_dsn (see config defaults).
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(VALID_DSN))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rejects_empty_body(public_client: AsyncClient, _configure_dsn):
    resp = await public_client.post("/api/sentry-tunnel", content=b"")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_mismatched_dsn(public_client: AsyncClient, _configure_dsn):
    """Envelopes pointing at a different Sentry project must be refused."""
    other = "https://xyz@o99999.ingest.sentry.io/1111111"
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(other))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_missing_dsn_in_envelope(
    public_client: AsyncClient, _configure_dsn
):
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(None))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_unparseable_header(public_client: AsyncClient, _configure_dsn):
    resp = await public_client.post("/api/sentry-tunnel", content=b"not-json\n{}\n{}\n")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_dsn_with_non_sentry_host(
    public_client: AsyncClient, monkeypatch
):
    """Hosts outside *.sentry.io are refused even if configured (defense in depth)."""
    bad = "https://abc@evil.example.com/123"
    monkeypatch.setattr(settings, "frontend_sentry_dsn", bad)
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(bad))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_rejects_dsn_with_non_numeric_project(
    public_client: AsyncClient, monkeypatch
):
    bad = "https://abc@o1.ingest.sentry.io/not-a-number"
    monkeypatch.setattr(settings, "frontend_sentry_dsn", bad)
    resp = await public_client.post("/api/sentry-tunnel", content=_envelope(bad))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_forwards_envelope_to_sentry(public_client: AsyncClient, _configure_dsn):
    """Successful path: body is POSTed to derived ingest URL, response relayed."""
    body = _envelope(VALID_DSN)

    upstream_response = MagicMock()
    upstream_response.status_code = 200
    upstream_response.content = b'{"id":"abc"}'

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=upstream_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rs_api.api.sentry_tunnel.httpx.AsyncClient", return_value=mock_client):
        resp = await public_client.post("/api/sentry-tunnel", content=body)

    assert resp.status_code == 200
    assert resp.content == b'{"id":"abc"}'

    mock_client.post.assert_awaited_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://o12345.ingest.sentry.io/api/4567890/envelope/"
    assert kwargs["content"] == body
    assert kwargs["headers"]["Content-Type"] == "application/x-sentry-envelope"


@pytest.mark.asyncio
async def test_returns_502_when_upstream_unreachable(
    public_client: AsyncClient, _configure_dsn
):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("boom"))
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rs_api.api.sentry_tunnel.httpx.AsyncClient", return_value=mock_client):
        resp = await public_client.post(
            "/api/sentry-tunnel", content=_envelope(VALID_DSN)
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_relays_upstream_error_status(public_client: AsyncClient, _configure_dsn):
    """Non-2xx responses from Sentry are passed through unchanged."""
    upstream_response = MagicMock()
    upstream_response.status_code = 429
    upstream_response.content = b'{"error":"rate limited"}'

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=upstream_response)
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("rs_api.api.sentry_tunnel.httpx.AsyncClient", return_value=mock_client):
        resp = await public_client.post(
            "/api/sentry-tunnel", content=_envelope(VALID_DSN)
        )

    assert resp.status_code == 429
    assert resp.content == b'{"error":"rate limited"}'
