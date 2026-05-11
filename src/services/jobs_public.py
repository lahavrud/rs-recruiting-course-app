"""Public job board service functions (no authentication required)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.enums import JobStatus
from src.models import Job
from src.schemas import JobPublicRead
from src.services.exceptions import JobNotFoundError


async def list_published_jobs(
    session: AsyncSession,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[JobPublicRead]:
    """One page of published jobs, newest first."""
    page_size = clamp_limit(limit)
    query = apply_cursor(
        select(Job).where(Job.status == JobStatus.PUBLISHED),  # pyright: ignore[reportArgumentType]
        sort_col=Job.created_at,  # pyright: ignore[reportArgumentType]
        id_col=Job.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=JobPublicRead.model_validate,
        cursor_key=lambda j: (j.created_at, j.id),
        limit=page_size,
    )


async def get_published_job(job_id: int, session: AsyncSession) -> JobPublicRead:
    """Get a published job by ID for public viewing.

    Args:
        job_id: ID of the job to retrieve
        session: Database session

    Returns:
        Job as JobPublicRead schema

    Raises:
        JobNotFoundError: If job not found or not published
    """
    job = await get_by_id_or_raise(
        session, Job, job_id, lambda pk: JobNotFoundError(f"Job with ID {pk} not found")
    )
    if job.status != JobStatus.PUBLISHED:
        raise JobNotFoundError(f"Job with ID {job_id} is not published")
    return JobPublicRead.model_validate(job)
