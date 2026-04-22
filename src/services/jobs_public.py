"""Public job board service functions (no authentication required)."""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import JobStatus
from src.models import Job
from src.schemas import JobPublicRead
from src.services.exceptions import JobNotFoundError


async def list_published_jobs(session: AsyncSession) -> list[JobPublicRead]:
    """List all published jobs for public job board.

    Args:
        session: Database session

    Returns:
        List of published jobs as JobPublicRead schemas,
        ordered by creation date (newest first)
    """
    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PUBLISHED)  # pyright: ignore[reportArgumentType]
        .order_by(desc(Job.created_at))  # pyright: ignore[reportArgumentType]
    )
    jobs = result.scalars().all()
    return [JobPublicRead.model_validate(job) for job in jobs]


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
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")
    if job.status != JobStatus.PUBLISHED:
        raise JobNotFoundError(f"Job with ID {job_id} is not published")
    return JobPublicRead.model_validate(job)
