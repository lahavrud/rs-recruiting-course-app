"""Tests for Arq task processing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.tasks import (
    WorkerSettings,
    enqueue_email_task,
    get_redis_pool,
    send_email_task,
)


@pytest.mark.asyncio
async def test_send_email_task_success():
    """Test successful email task execution."""
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = True
        mock_get_provider.return_value = mock_provider

        result = await send_email_task(
            ctx={},
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        mock_provider.send_email.assert_called_once_with(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email=None,
        )


@pytest.mark.asyncio
async def test_send_email_task_failure_raises_exception():
    """Test that email task raises exception on failure to trigger retry."""
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = False
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="Email provider returned False"):
            await send_email_task(
                ctx={},
                to="test@example.com",
                subject="Test Subject",
                body="Test Body",
            )


@pytest.mark.asyncio
async def test_send_email_task_provider_exception():
    """Test that provider exceptions are re-raised for retry."""
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.side_effect = Exception("SMTP connection failed")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="SMTP connection failed"):
            await send_email_task(
                ctx={},
                to="test@example.com",
                subject="Test Subject",
                body="Test Body",
            )


@pytest.mark.asyncio
async def test_send_email_task_multiple_recipients():
    """Test email task with multiple recipients."""
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = True
        mock_get_provider.return_value = mock_provider

        recipients = ["user1@example.com", "user2@example.com"]
        result = await send_email_task(
            ctx={},
            to=recipients,
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        mock_provider.send_email.assert_called_once_with(
            to=recipients,
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email=None,
        )


@pytest.mark.asyncio
async def test_send_email_task_with_from_email():
    """Test email task with custom from_email."""
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = True
        mock_get_provider.return_value = mock_provider

        result = await send_email_task(
            ctx={},
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email="custom@example.com",
        )

        assert result is True
        mock_provider.send_email.assert_called_once_with(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email="custom@example.com",
        )


@pytest.mark.asyncio
async def test_enqueue_email_task_success():
    """Test successfully enqueueing an email task."""
    with patch("src.core.tasks.get_redis_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_job = MagicMock()
        mock_job.job_id = "test-job-123"
        mock_pool.enqueue_job.return_value = mock_job
        mock_get_pool.return_value = mock_pool

        job_id = await enqueue_email_task(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert job_id == "test-job-123"
        mock_pool.enqueue_job.assert_called_once_with(
            "send_email_task",
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
            html_body=None,
            attachments=None,
            from_email=None,
        )


@pytest.mark.asyncio
async def test_enqueue_email_task_failure_returns_none():
    """Test that enqueue failure returns None."""
    with patch("src.core.tasks.get_redis_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_pool.enqueue_job.side_effect = Exception("Redis connection failed")
        mock_get_pool.return_value = mock_pool

        job_id = await enqueue_email_task(
            to="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert job_id is None


@pytest.mark.asyncio
async def test_get_redis_pool_creates_pool():
    """Test that get_redis_pool creates a new pool if none exists."""
    with patch("src.core.tasks.create_pool") as mock_create_pool:
        # Reset global pool
        import src.core.tasks

        src.core.tasks._redis_pool = None

        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        pool = await get_redis_pool()

        assert pool == mock_pool
        mock_create_pool.assert_called_once()


@pytest.mark.asyncio
async def test_get_redis_pool_reuses_existing_pool():
    """Test that get_redis_pool reuses existing pool."""
    with patch("src.core.tasks.create_pool") as mock_create_pool:
        import src.core.tasks

        # Set existing pool
        existing_pool = AsyncMock()
        src.core.tasks._redis_pool = existing_pool

        pool = await get_redis_pool()

        assert pool == existing_pool
        mock_create_pool.assert_not_called()

        # Cleanup
        src.core.tasks._redis_pool = None


def test_worker_settings_configuration():
    """Test WorkerSettings configuration."""
    settings = WorkerSettings()

    assert settings.functions == [send_email_task]
    assert settings.max_jobs == 10
    assert settings.job_timeout == 300
    assert settings.retry_jobs is True
    assert settings.max_tries == 3
    assert settings.keep_result == 3600
