"""Email quota tracking and alerting.

Maintains a daily counter in the ``email_quota`` table. After each successful
send the worker calls ``increment_and_alert``, which bumps today's row and
emits log warnings as the free-tier limits approach.

No hard enforcement is applied here — Resend's own 429 response is the
backstop. The goal is to surface usage before the ceiling is hit.
"""

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.core.infrastructure.config import settings

logger = logging.getLogger(__name__)

_THRESHOLDS = (0.5, 0.75, 0.9, 1.0)


async def increment_and_alert(session: AsyncSession) -> None:
    """Increment today's send counter and log warnings at quota thresholds."""
    today = date.today()

    await session.execute(
        text(
            "INSERT INTO email_quota (date, count) VALUES (:d, 1) "
            "ON CONFLICT (date) DO UPDATE SET count = email_quota.count + 1"
        ),
        {"d": today},
    )

    daily_count: int = (
        await session.execute(
            text("SELECT count FROM email_quota WHERE date = :d"),
            {"d": today},
        )
    ).scalar_one()

    first_of_month = today.replace(day=1)
    monthly_count: int = (
        await session.execute(
            text("SELECT COALESCE(SUM(count), 0) FROM email_quota WHERE date >= :m"),
            {"m": first_of_month},
        )
    ).scalar_one()

    _check(daily_count, settings.email_daily_limit, "daily")
    _check(monthly_count, settings.email_monthly_limit, "monthly")


def _check(count: int, limit: int, label: str) -> None:
    ratio = count / limit if limit else 0
    for threshold in reversed(_THRESHOLDS):
        if ratio >= threshold:
            pct = int(threshold * 100)
            extra = {"count": count, "limit": limit, "label": label}
            if threshold >= 1.0:
                logger.critical("email_quota_exceeded", extra=extra)
            elif threshold >= 0.9:
                logger.critical("email_quota_%d_pct" % pct, extra=extra)
            else:
                logger.warning("email_quota_%d_pct" % pct, extra=extra)
            return
