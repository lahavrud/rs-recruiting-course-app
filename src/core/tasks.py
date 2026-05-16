"""Arq task definitions for async background job processing."""

import logging
from typing import List, Optional

import aioboto3
from arq import ArqRedis, create_pool
from arq.connections import RedisSettings
from arq.cron import cron

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import async_session
from src.core.infrastructure.transactions import transactional
from src.core.services.email import get_email_provider
from src.services.candidates_admin import purge_expired_candidates

logger = logging.getLogger(__name__)

# CloudWatch namespace for our application metrics. Single namespace keeps
# the alarm/dashboard surface uniform and the IAM policy tight.
METRIC_NAMESPACE = "RsRecruitment/Retention"

# Global Redis pool (initialized on worker startup)
_redis_pool: Optional[ArqRedis] = None


async def send_email_task(
    ctx: dict,
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> bool:
    """Async task to send an email, processed by Arq workers with auto-retry."""
    logger.info(f"Sending email to {to} with subject: {subject}")

    try:
        provider = get_email_provider()
        success = await provider.send_email(
            to=to,
            subject=subject,
            body=body,
            html_body=html_body,
            attachments=attachments,
            from_email=from_email,
        )

        if success:
            logger.info(f"Email sent successfully to {to}")
        else:
            logger.warning(f"Failed to send email to {to}")
            raise Exception(f"Email provider returned False for {to}")

        return success
    except Exception as e:
        logger.error(f"Error sending email to {to}: {e}", exc_info=True)
        raise


async def _emit_purge_count_metric(count: int) -> None:
    """Emit PurgedCandidatesCount to CloudWatch (production only).

    Always emits a datapoint — even count=0 — so a stale-purge alarm can
    detect a dead worker via missing data. Failures are swallowed: the
    purge already happened in the DB, and we don't want a metrics blip
    to mask compliance success.
    """
    if settings.environment != "production":
        return
    try:
        session = aioboto3.Session()
        async with session.client("cloudwatch", region_name=settings.aws_region) as cw:
            await cw.put_metric_data(
                Namespace=METRIC_NAMESPACE,
                MetricData=[
                    {
                        "MetricName": "PurgedCandidatesCount",
                        "Value": float(count),
                        "Unit": "Count",
                    }
                ],
            )
    except Exception:
        logger.exception("Failed to emit PurgedCandidatesCount metric")


async def purge_expired_candidate_data_task(ctx: dict) -> int:
    """Periodic task: purge candidates past the 12-month retention window.

    Runs nightly via Arq cron. The heavy lifting lives in
    ``src.services.candidates_admin.purge_expired_candidates``; this
    wrapper just opens a session, delegates, and emits the count metric.
    """
    async with async_session() as session:
        async with transactional(session):
            count = await purge_expired_candidates(session)
    await _emit_purge_count_metric(count)
    return count


class WorkerSettings:
    """Arq worker configuration."""

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [send_email_task, purge_expired_candidate_data_task]
    cron_jobs = [
        # Nightly at 03:00 UTC — off-peak for our user base.
        cron(purge_expired_candidate_data_task, hour=3, minute=0),
    ]
    # Retry configuration
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = 300  # 5 minutes timeout per job
    # Retry failed tasks up to 3 times with exponential backoff
    retry_jobs = True
    max_tries = 3
    # Keep job results for 1 hour
    keep_result = 3600


async def get_redis_pool() -> ArqRedis:
    """
    Get or create Redis connection pool for Arq.

    The pool is created lazily on first use (not during application startup).
    This allows the application to start even if Redis is temporarily unavailable.

    Returns:
        ArqRedis connection pool instance

    Raises:
        ConnectionError: If unable to connect to Redis
    """
    global _redis_pool

    if _redis_pool is None:
        try:
            redis_settings = RedisSettings.from_dsn(settings.redis_url)
            _redis_pool = await create_pool(redis_settings)
            logger.info(f"Created Redis connection pool: {settings.redis_url}")
        except Exception as e:
            logger.error(
                f"Failed to connect to Redis at {settings.redis_url}: {e}. "
                "Make sure Redis is running and REDIS_URL is configured correctly."
            )
            raise

    return _redis_pool


async def close_redis_pool() -> None:
    """Close Redis connection pool (call on application shutdown)."""
    global _redis_pool

    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None
        logger.info("Closed Redis connection pool")


async def enqueue_email_task(
    to: str | List[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[tuple]] = None,
    from_email: Optional[str] = None,
) -> str:
    """Enqueue an email task for async processing via Arq workers.

    Raises on any Redis / Arq failure so callers are never silently
    missing email sends.  Call sites inside transactional blocks should
    use defer_after_commit so the DB write is not rolled back on an Arq
    outage.
    """
    pool = await get_redis_pool()
    job = await pool.enqueue_job(
        "send_email_task",
        to=to,
        subject=subject,
        body=body,
        html_body=html_body,
        attachments=attachments,
        from_email=from_email,
    )
    logger.info(f"Enqueued email task {job.job_id} for {to}")
    return job.job_id
