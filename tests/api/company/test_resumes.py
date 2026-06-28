"""Integration tests for the resume download endpoint."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_download_resume_requires_admin(public_client: AsyncClient):
    """Unauthenticated clients cannot download resumes."""
    response = await public_client.get("/api/resumes/test.pdf")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_download_resume_invalid_key(admin_client: AsyncClient):
    """Returns 400 for keys containing characters outside the safe set."""
    response = await admin_client.get("/api/resumes/invalid@key.pdf")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_download_resume_not_found(admin_client: AsyncClient, tmp_path: Path):
    """Returns 404 when the file does not exist in storage."""
    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/nonexistent.pdf")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_resume_success(admin_client: AsyncClient, tmp_path: Path):
    """Returns 200 and file content for a valid existing resume.

    Files live under `<storage>/resumes/<key>` (storage providers prepend
    the `resumes/` prefix on upload); the route re-adds that prefix before
    reading from disk.
    """
    fake_pdf = b"%PDF-1.4 fake content"
    resumes_dir = tmp_path / "resumes"
    resumes_dir.mkdir()
    (resumes_dir / "resume.pdf").write_bytes(fake_pdf)

    mock_settings = MagicMock()
    mock_settings.storage_provider = "local"
    mock_settings.local_storage_path = str(tmp_path)

    with patch("rs_api.api._resume_streaming.settings", mock_settings):
        response = await admin_client.get("/api/resumes/resume.pdf")

    assert response.status_code == 200
    assert response.content == fake_pdf


@pytest.mark.asyncio
async def test_download_resume_s3_proxies(admin_client: AsyncClient):
    """For S3 storage, streams the file bytes directly (no redirect).

    The key passed to the storage provider must include the `resumes/` prefix,
    since that's where files actually live under the bucket.
    """
    mock_settings = MagicMock()
    mock_settings.storage_provider = "s3"

    fake_pdf = b"%PDF-1.4 fake s3 content"
    received_keys: list[str] = []

    async def fake_download(key: str) -> bytes:
        received_keys.append(key)
        return fake_pdf

    mock_storage = MagicMock()
    mock_storage.download_file = fake_download

    with (
        patch("rs_api.api._resume_streaming.settings", mock_settings),
        patch(
            "rs_api.api._resume_streaming.get_storage_provider",
            return_value=mock_storage,
        ),
    ):
        response = await admin_client.get("/api/resumes/abc123.pdf")

    assert response.status_code == 200
    assert response.content == fake_pdf
    assert response.headers["content-type"] == "application/pdf"
    assert received_keys == ["resumes/abc123.pdf"]
