"""Tests for SQS task producer and task implementations."""

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.tasks import (
    TASK_REGISTRY,
    enqueue_data_export_task,
    enqueue_email_task,
    purge_expired_candidate_data_task,
    send_email_task,
)

# ---------------------------------------------------------------------------
# send_email_task — implementation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_task_success():
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)
    txn_cm = MagicMock()
    txn_cm.__aenter__ = AsyncMock(return_value=None)
    txn_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("src.core.tasks.get_email_provider") as mock_get_provider,
        patch("src.core.tasks.async_session", return_value=session_cm),
        patch("src.core.tasks.transactional", return_value=txn_cm),
        patch("src.core.tasks.increment_and_alert", new_callable=AsyncMock),
    ):
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = True
        mock_get_provider.return_value = mock_provider

        result = await send_email_task(
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
async def test_send_email_task_provider_returns_false_raises():
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.return_value = False
        mock_get_provider.return_value = mock_provider

        with pytest.raises(RuntimeError, match="Email provider returned False"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")


@pytest.mark.asyncio
async def test_send_email_task_provider_exception_propagates():
    with patch("src.core.tasks.get_email_provider") as mock_get_provider:
        mock_provider = AsyncMock()
        mock_provider.send_email.side_effect = Exception("SMTP connection failed")
        mock_get_provider.return_value = mock_provider

        with pytest.raises(Exception, match="SMTP connection failed"):
            await send_email_task(to="test@example.com", subject="Subject", body="Body")


# ---------------------------------------------------------------------------
# enqueue_email_task — inline path (SQS_QUEUE_URL not configured)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_email_task_inline_when_no_queue_url():
    """When SQS_QUEUE_URL is empty the task runs inline and returns 'inline'."""
    with (
        patch("src.core.tasks.settings") as mock_settings,
        patch("src.core.tasks.send_email_task", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.sqs_queue_url = ""
        mock_send.return_value = True

        result = await enqueue_email_task(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

    assert result == "inline"
    mock_send.assert_awaited_once_with(
        to="test@example.com",
        subject="Subject",
        body="Body",
        html_body=None,
        attachments=None,
        from_email=None,
    )


# ---------------------------------------------------------------------------
# enqueue_email_task — SQS path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_email_task_sends_to_sqs():
    """When SQS_QUEUE_URL is set, a message is sent and the MessageId returned."""
    with (
        patch("src.core.tasks.settings") as mock_settings,
        patch("src.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "msg-id-abc"

        result = await enqueue_email_task(
            to="test@example.com",
            subject="Subject",
            body="Body",
        )

    assert result == "msg-id-abc"
    payload = mock_sqs.call_args[0][0]
    assert payload["task"] == "send_email"
    assert payload["to"] == "test@example.com"
    assert payload["attachments"] is None


@pytest.mark.asyncio
async def test_enqueue_email_task_base64_encodes_attachments():
    """Attachment bytes are base64-encoded for JSON-safe transport over SQS."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"

    with (
        patch("src.core.tasks.settings") as mock_settings,
        patch("src.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "msg-id-xyz"

        await enqueue_email_task(
            to="test@example.com",
            subject="Contract",
            body="See attached.",
            attachments=[("contract.pdf", pdf_bytes, "application/pdf")],
        )

    payload = mock_sqs.call_args[0][0]
    name, encoded, mime = payload["attachments"][0]
    assert name == "contract.pdf"
    assert mime == "application/pdf"
    assert base64.b64decode(encoded) == pdf_bytes


# ---------------------------------------------------------------------------
# enqueue_data_export_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_data_export_task_sends_to_sqs():
    with (
        patch("src.core.tasks.settings") as mock_settings,
        patch("src.core.tasks._sqs_send", new_callable=AsyncMock) as mock_sqs,
    ):
        mock_settings.sqs_queue_url = "https://sqs.us-east-1.amazonaws.com/123/queue"
        mock_sqs.return_value = "export-msg-id"

        result = await enqueue_data_export_task(user_id=42)

    assert result == "export-msg-id"
    payload = mock_sqs.call_args[0][0]
    assert payload == {"task": "build_data_export", "user_id": 42}


# ---------------------------------------------------------------------------
# TASK_REGISTRY — completeness
# ---------------------------------------------------------------------------


def test_task_registry_contains_expected_tasks():
    assert "send_email" in TASK_REGISTRY
    assert "build_data_export" in TASK_REGISTRY
    assert "purge_expired_candidates" in TASK_REGISTRY


# ---------------------------------------------------------------------------
# purge_expired_candidate_data_task — CloudWatch observability
# ---------------------------------------------------------------------------


def _patch_purge_returning(count: int):
    return patch(
        "src.services.admin.candidates.purge_expired_candidates",
        new=AsyncMock(return_value=count),
    )


def _patch_session_noop():
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

        result = await purge_expired_candidate_data_task()

    assert result == 7
    cw_client.put_metric_data.assert_awaited_once()
    call_kwargs = cw_client.put_metric_data.await_args.kwargs
    assert call_kwargs["Namespace"] == "RsRecruiting/Retention"
    [datum] = call_kwargs["MetricData"]
    assert datum["MetricName"] == "PurgedCandidatesCount"
    assert datum["Value"] == 7.0


@pytest.mark.asyncio
async def test_purge_task_emits_zero_on_empty_run():
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

        await purge_expired_candidate_data_task()

    cw_client.put_metric_data.assert_awaited_once()
    [datum] = cw_client.put_metric_data.await_args.kwargs["MetricData"]
    assert datum["Value"] == 0.0


@pytest.mark.asyncio
async def test_purge_task_skips_metric_outside_production():
    s_patch, t_patch = _patch_session_noop()
    with (
        _patch_purge_returning(3),
        s_patch,
        t_patch,
        patch("src.core.tasks.aioboto3.Session") as boto_session_cls,
        patch("src.core.tasks.settings") as mock_settings,
    ):
        mock_settings.environment = "development"

        result = await purge_expired_candidate_data_task()

    assert result == 3
    boto_session_cls.assert_not_called()


@pytest.mark.asyncio
async def test_purge_task_swallows_metric_failure():
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

        result = await purge_expired_candidate_data_task()

    assert result == 2
