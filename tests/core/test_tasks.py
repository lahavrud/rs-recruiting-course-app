"""Tests for Arq task processing."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.tasks import (
    WorkerSettings,
    enqueue_email_task,
    get_redis_pool,
    purge_expired_candidate_data_task,
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
async def test_enqueue_email_task_failure_raises():
    """Test that enqueue failure propagates the exception to the caller."""
    with patch("src.core.tasks.get_redis_pool") as mock_get_pool:
        mock_pool = AsyncMock()
        mock_pool.enqueue_job.side_effect = Exception("Redis connection failed")
        mock_get_pool.return_value = mock_pool

        with pytest.raises(Exception, match="Redis connection failed"):
            await enqueue_email_task(
                to="test@example.com",
                subject="Test Subject",
                body="Test Body",
            )


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

    assert settings.functions == [send_email_task, purge_expired_candidate_data_task]
    assert settings.max_jobs == 10
    assert settings.job_timeout == 300
    assert settings.retry_jobs is True
    assert settings.max_tries == 3
    assert settings.keep_result == 3600


# ── purge_expired_candidate_data_task — observability ────────────────────────


def _patch_purge_returning(count: int):
    """Patch the service function to return ``count`` without touching the DB."""
    return patch(
        "src.core.tasks.purge_expired_candidates",
        new=AsyncMock(return_value=count),
    )


def _patch_session_noop():
    """Patch async_session + transactional so the task doesn't hit the DB."""
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)

    txn_cm = MagicMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=None)

    return (
        patch("src.core.tasks.async_session", return_value=session_cm),
        patch("src.core.tasks.transactional", return_value=txn_cm),
    )


@pytest.mark.asyncio
async def test_purge_task_emits_metric_in_production():
    """In production, the task emits PurgedCandidatesCount with the count."""
    cw_client = AsyncMock()
    cw_client.__aenter__.return_value = cw_client
    cw_client.__aexit__.return_value = None
    boto_session = MagicMock()
    boto_session.client.return_value = cw_client

    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(7),
        s_patch,
        t_patch,
        patch("src.core.tasks.aioboto3.Session", return_value=boto_session),
        patch("src.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "production"
        mock_settings.aws_region = "us-east-1"

        result = await purge_expired_candidate_data_task(ctx={})

    assert result == 7
    cw_client.put_metric_data.assert_awaited_once()
    call_kwargs = cw_client.put_metric_data.await_args.kwargs
    assert call_kwargs["Namespace"] == "RsRecruiting/Retention"
    [datum] = call_kwargs["MetricData"]
    assert datum["MetricName"] == "PurgedCandidatesCount"
    assert datum["Value"] == 7.0
    assert datum["Unit"] == "Count"


@pytest.mark.asyncio
async def test_purge_task_emits_zero_on_empty_run():
    """Empty runs still emit a datapoint — required for the missing-data alarm."""
    cw_client = AsyncMock()
    cw_client.__aenter__.return_value = cw_client
    cw_client.__aexit__.return_value = None
    boto_session = MagicMock()
    boto_session.client.return_value = cw_client

    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(0),
        s_patch,
        t_patch,
        patch("src.core.tasks.aioboto3.Session", return_value=boto_session),
        patch("src.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "production"
        mock_settings.aws_region = "us-east-1"

        await purge_expired_candidate_data_task(ctx={})

    cw_client.put_metric_data.assert_awaited_once()
    [datum] = cw_client.put_metric_data.await_args.kwargs["MetricData"]
    assert datum["Value"] == 0.0


@pytest.mark.asyncio
async def test_purge_task_skips_metric_outside_production():
    """In dev/test, no metric is emitted (avoids polluting CloudWatch and IAM noise)."""
    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(3),
        s_patch,
        t_patch,
        patch("src.core.tasks.aioboto3.Session") as boto_session_cls,
        patch("src.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "development"

        result = await purge_expired_candidate_data_task(ctx={})

    assert result == 3
    boto_session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_purge_task_swallows_metric_failure():
    """A CloudWatch failure must not mask the purge or raise from the task."""
    cw_client = AsyncMock()
    cw_client.__aenter__.return_value = cw_client
    cw_client.__aexit__.return_value = None
    cw_client.put_metric_data.side_effect = RuntimeError("CW outage")
    boto_session = MagicMock()
    boto_session.client.return_value = cw_client

    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(2),
        s_patch,
        t_patch,
        patch("src.core.tasks.aioboto3.Session", return_value=boto_session),
        patch("src.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "production"
        mock_settings.aws_region = "us-east-1"

        result = await purge_expired_candidate_data_task(ctx={})

    assert result == 2  # purge succeeded; metric failure is invisible to caller
