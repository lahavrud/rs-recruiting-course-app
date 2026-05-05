"""Admin job approval service functions."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks import enqueue_email_task
from src.enums import JobStatus
from src.models import CompanyProfile, Job, User
from src.schemas import JobRead
from src.services.exceptions import JobNotFoundError, JobNotPendingError
from src.templates.email import build_job_contact_html


async def list_pending_jobs(session: AsyncSession) -> list[JobRead]:
    """List all pending jobs for admin approval.

    Args:
        session: Database session

    Returns:
        List of pending jobs as JobRead schemas, ordered by creation date (oldest first)
    """
    result = await session.execute(
        select(Job)
        .where(Job.status == JobStatus.PENDING_APPROVAL)  # pyright: ignore[reportArgumentType]
        .order_by(Job.created_at)  # pyright: ignore[reportArgumentType]
    )
    jobs = result.scalars().all()
    return [JobRead.model_validate(job) for job in jobs]


async def approve_job(job_id: int, session: AsyncSession) -> JobRead:
    """Approve a job posting by changing status to PUBLISHED.

    Sets Job.status=PUBLISHED and sends email notification to the company.

    Args:
        job_id: ID of the job to approve
        session: Database session

    Returns:
        Approved job as JobRead schema

    Raises:
        JobNotFoundError: If job not found
        JobNotPendingError: If job is not pending approval
    """
    # Get the job
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    # Validate it's pending
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobNotPendingError(
            f"Job {job_id} is not pending approval (current status: {job.status})"
        )

    # Approve the job
    job.status = JobStatus.PUBLISHED
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Get company and user for email
    # Foreign key constraints guarantee company and user exist
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == job.company_id)  # pyright: ignore[reportArgumentType]
    )
    company = result.scalar_one()
    result = await session.execute(
        select(User).where(User.id == company.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()

    # Send approval email to company
    await enqueue_email_task(
        to=user.email,
        subject="Job Posting Approved",
        body=(
            f"Your job posting '{job.title}' has been approved "
            f"and is now published on the job board.\n\n"
            f"Job Title: {job.title}\n"
            f"Location: {job.location}\n"
            f"Job ID: {job.id}\n\n"
            "Candidates can now view and apply for this position."
        ),
    )

    return JobRead.model_validate(job)


async def reject_job(job_id: int, session: AsyncSession) -> None:
    """Reject a job posting by changing status to CLOSED.

    Sets Job.status=CLOSED and sends email notification to the company.

    Args:
        job_id: ID of the job to reject
        session: Database session

    Raises:
        JobNotFoundError: If job not found
        JobNotPendingError: If job is not pending approval
    """
    # Get the job
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    # Validate it's pending
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobNotPendingError(
            f"Job {job_id} is not pending approval (current status: {job.status})"
        )

    # Get company and user for email before updating
    # Foreign key constraints guarantee company and user exist
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == job.company_id)  # pyright: ignore[reportArgumentType]
    )
    company = result.scalar_one()
    result = await session.execute(
        select(User).where(User.id == company.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()
    job_title = job.title
    job_location = job.location

    # Reject the job (set status to CLOSED)
    job.status = JobStatus.CLOSED
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Send rejection email to company
    await enqueue_email_task(
        to=user.email,
        subject="Job Posting Rejected",
        body=(
            f"Your job posting '{job_title}' has been rejected "
            f"and will not be published.\n\n"
            f"Job Title: {job_title}\n"
            f"Location: {job_location}\n"
            f"Job ID: {job_id}\n\n"
            "If you believe this is an error, please contact support "
            "or update the job posting and resubmit for approval."
        ),
    )


async def contact_job(job_id: int, admin_note: str, session: AsyncSession) -> None:
    """Send a contextual email from admin to the company owning a job posting.

    The job may be in any status — this is a pre-decision communication tool.

    Args:
        job_id: ID of the job being discussed
        admin_note: Optional message body from the admin
        session: Database session

    Raises:
        JobNotFoundError: If job not found
    """
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == job.company_id)  # pyright: ignore[reportArgumentType]
    )
    company = result.scalar_one()
    result = await session.execute(
        select(User).where(User.id == company.user_id)  # pyright: ignore[reportArgumentType]
    )
    user = result.scalar_one()

    plain = (
        f"פנייה ממנהל המערכת בנוגע למשרת '{job.title}'.\n\n"
        f"{admin_note}\n\n"
        "לשאלות ופניות נוספות, אנא צרו קשר עם צוות RS Recruiting."
    )
    await enqueue_email_task(
        to=user.email,
        subject="פנייה בנוגע למשרה — RS Recruiting",
        body=plain,
        html_body=build_job_contact_html(
            job_title=job.title,
            company_name=company.name,
            admin_note=admin_note,
        ),
    )
