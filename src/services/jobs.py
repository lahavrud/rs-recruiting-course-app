"""Job service layer for business logic."""

from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks import enqueue_email_task
from src.enums import JobStatus
from src.models import CompanyProfile, Job
from src.schemas import JobCreate, JobRead, JobUpdate
from src.services.admin_companies import get_all_admin_emails
from src.services.exceptions import (
    CompanyNotFoundError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
)
from src.templates.email import build_job_updated_html, build_new_job_html


async def create_job(
    job_data: JobCreate, company_id: int, session: AsyncSession
) -> JobRead:
    """Create a new job posting.

    Jobs are created with PENDING_APPROVAL status and require admin approval.
    Sends email notification to all admins.

    Args:
        job_data: Job creation data
        company_id: ID of the company creating the job
        session: Database session

    Returns:
        Created job as JobRead schema

    Raises:
        CompanyNotFoundError: If company not found
    """
    # Verify company exists
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)  # pyright: ignore[reportArgumentType]
    )
    company = result.scalar_one_or_none()
    if not company:
        raise CompanyNotFoundError(f"Company with ID {company_id} not found")

    # Create job with PENDING_APPROVAL status
    new_job = Job(
        company_id=company_id,
        title=job_data.title,
        description=job_data.description,
        requirements=job_data.requirements,
        location=job_data.location,
        status=JobStatus.PENDING_APPROVAL,
    )
    session.add(new_job)
    await session.flush()

    # Send email notification to all admins
    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        from src.core.infrastructure.config import settings

        admin_url = f"{settings.frontend_base_url}/admin/jobs"
        plain = f"משרה חדשה ממתינה לאישור: {new_job.title} ({company.name})"
        html = build_new_job_html(
            job_title=new_job.title,
            company_name=company.name or "",
            location=new_job.location,
            job_id=new_job.id or 0,
            admin_url=admin_url,
        )
        await enqueue_email_task(
            to=admin_emails,
            subject="משרה חדשה ממתינה לאישור – RS Recruiting",
            body=plain,
            html_body=html,
        )

    return JobRead.model_validate(new_job)


async def get_job(job_id: int, session: AsyncSession) -> JobRead:
    """Get a job by ID.

    Args:
        job_id: ID of the job to retrieve
        session: Database session

    Returns:
        Job as JobRead schema

    Raises:
        JobNotFoundError: If job not found
    """
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")
    return JobRead.model_validate(job)


async def list_company_jobs(company_id: int, session: AsyncSession) -> list[JobRead]:
    """List all jobs for a company.

    Args:
        company_id: ID of the company
        session: Database session

    Returns:
        List of jobs as JobRead schemas
    """
    result = await session.execute(
        select(Job)
        .where(Job.company_id == company_id)  # pyright: ignore[reportArgumentType]
        .order_by(desc(Job.created_at))  # pyright: ignore[reportArgumentType]
    )
    jobs = result.scalars().all()
    return [JobRead.model_validate(job) for job in jobs]


async def update_job(
    job_id: int,
    job_data: JobUpdate,
    company_id: int,
    session: AsyncSession,
) -> JobRead:
    """Update a job posting.

    Only the company owner can update their jobs.
    Jobs can only be updated if status is PENDING_APPROVAL or PUBLISHED.
    Status cannot be changed by company (only admin can change status).
    Sends email notification to admins when job is updated.

    Args:
        job_id: ID of the job to update
        job_data: Job update data
        company_id: ID of the company making the update (for ownership verification)
        session: Database session

    Returns:
        Updated job as JobRead schema

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
        JobCannotBeUpdatedError: If job status doesn't allow updates
    """
    # Get the job
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    # Verify ownership
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    # Verify job can be updated (only PENDING_APPROVAL or PUBLISHED)
    if job.status not in (JobStatus.PENDING_APPROVAL, JobStatus.PUBLISHED):
        raise JobCannotBeUpdatedError(
            f"Job {job_id} with status {job.status} cannot be updated"
        )

    # Companies cannot change status (only admin can)
    if job_data.status is not None and job_data.status != job.status:
        raise JobCannotBeUpdatedError("Companies cannot change job status")

    # Update fields
    if job_data.title is not None:
        job.title = job_data.title
    if job_data.description is not None:
        job.description = job_data.description
    if job_data.requirements is not None:
        job.requirements = job_data.requirements
    if job_data.location is not None:
        job.location = job_data.location

    # Update updated_at timestamp
    job.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Get company for email
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)  # pyright: ignore[reportArgumentType]
    )
    company = result.scalar_one()

    # Send email notification to all admins
    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        from src.core.infrastructure.config import settings

        admin_url = f"{settings.frontend_base_url}/admin/jobs"
        plain = f"פרסום משרה עודכן: {job.title} ({company.name})"
        html = build_job_updated_html(
            job_title=job.title,
            company_name=company.name or "",
            location=job.location,
            job_id=job.id or 0,
            status=str(job.status),
            admin_url=admin_url,
        )
        await enqueue_email_task(
            to=admin_emails,
            subject="פרסום משרה עודכן – RS Recruiting",
            body=plain,
            html_body=html,
        )

    return JobRead.model_validate(job)


async def delete_job(job_id: int, company_id: int, session: AsyncSession) -> None:
    """Delete a job posting.

    Only the company owner can delete their jobs.
    Jobs can only be deleted if status is PENDING_APPROVAL.

    Args:
        job_id: ID of the job to delete
        company_id: ID of the company making the delete (for ownership verification)
        session: Database session

    Raises:
        JobNotFoundError: If job not found
        JobNotOwnedByCompanyError: If job is not owned by the company
        JobCannotBeDeletedError: If job status doesn't allow deletion
    """
    # Get the job
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    # Verify ownership
    if job.company_id != company_id:
        raise JobNotOwnedByCompanyError(
            f"Job {job_id} is not owned by company {company_id}"
        )

    # Verify job can be deleted (only PENDING_APPROVAL)
    if job.status != JobStatus.PENDING_APPROVAL:
        raise JobCannotBeDeletedError(
            f"Job {job_id} with status {job.status} cannot be deleted. "
            "Only jobs with PENDING_APPROVAL status can be deleted."
        )

    # Delete the job
    await session.delete(job)
    await session.flush()
