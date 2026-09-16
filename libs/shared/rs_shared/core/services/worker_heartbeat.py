"""Worker version heartbeat.

The SQS worker has no HTTP surface, so a deploy pipeline can't poll it directly
to confirm a release converged. On startup the worker upserts its running image
tag into the singleton ``worker_heartbeat`` row (id=1); the api's ``/health``
reads it back as ``worker_version``, giving smoke checks a public convergence
signal for a worker release — mirroring how ``/health``'s ``version`` reports
the api's own image tag.

Written via a raw-SQL upsert (like ``email_quota``); the ``WorkerHeartbeat``
model exists so ``create_all`` builds the table in dev/test. Callers own the
transaction — this module never commits.
"""

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Single-row table: every worker boot upserts the same row.
_SINGLETON_ID = 1


async def record_heartbeat(session: AsyncSession, version: str) -> None:
    """Upsert the worker's running version into the singleton heartbeat row."""
    await session.execute(
        text(
            "INSERT INTO worker_heartbeat (id, version, updated_at) "
            "VALUES (:id, :v, :ts) "
            "ON CONFLICT (id) DO UPDATE SET version = :v, updated_at = :ts"
        ),
        {"id": _SINGLETON_ID, "v": version, "ts": datetime.now(timezone.utc)},
    )


async def read_worker_version(session: AsyncSession) -> str | None:
    """Return the worker's last-recorded version, or None if never recorded."""
    return (
        await session.execute(
            text("SELECT version FROM worker_heartbeat WHERE id = :id"),
            {"id": _SINGLETON_ID},
        )
    ).scalar_one_or_none()
