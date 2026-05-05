"""Admin service functions for application (match) management."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from src.schemas import ApplicationRead, ApplicationWithDetails
from src.services.exceptions import (
    ApplicationNotFoundError,
    InvalidApplicationStatusTransitionError,
)

# Valid status transitions — terminal states (REJECTED, HIRED) have no outgoing edges
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.NEW: {
        ApplicationStatus.APPROVED_BY_ADMIN,
        ApplicationStatus.REJECTED,
    },
    ApplicationStatus.APPROVED_BY_ADMIN: {
        ApplicationStatus.HIRED,
        ApplicationStatus.REJECTED,
    },
}


async def list_applications(
    session: AsyncSession,
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
) -> list[ApplicationWithDetails]:
    """List all applications with optional filters.

    Args:
        session: Database session
        status: Filter by application status (optional)
        job_id: Filter by job ID (optional)
        candidate_id: Filter by candidate ID (optional)

    Returns:
        List of applications with nested job and candidate details,
        ordered by creation date (newest first)
    """
    query = (
        select(Application)
        .options(
            selectinload(Application.job),  # pyright: ignore[reportArgumentType]
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
        )
        .order_by(Application.created_at.desc())  # pyright: ignore[reportArgumentType]
    )

    if status is not None:
        query = query.where(Application.status == status)  # pyright: ignore[reportArgumentType]
    if job_id is not None:
        query = query.where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    if candidate_id is not None:
        query = query.where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]

    result = await session.execute(query)
    applications = result.scalars().all()
    return [ApplicationWithDetails.model_validate(app) for app in applications]


async def get_application(
    application_id: int, session: AsyncSession
) -> ApplicationWithDetails:
    """Get a single application with full details.

    Args:
        application_id: ID of the application to retrieve
        session: Database session

    Returns:
        Application with nested job and candidate details

    Raises:
        ApplicationNotFoundError: If application not found
    """
    result = await session.execute(
        select(Application)
        .options(
            selectinload(Application.job),  # pyright: ignore[reportArgumentType]
            selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
        )
        .where(Application.id == application_id)  # pyright: ignore[reportArgumentType]
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )
    return ApplicationWithDetails.model_validate(application)


async def update_application_status(
    application_id: int,
    new_status: ApplicationStatus,
    session: AsyncSession,
    admin_notes: str | None = None,
) -> tuple[ApplicationRead, list[dict[str, str]]]:
    """Update an application's status and optionally add admin notes.

    Enforces valid status transitions. Returns the updated application and
    a list of email payloads to be enqueued by the caller *after* the
    surrounding DB transaction has been committed, so emails are never sent
    for changes that were subsequently rolled back.

    Args:
        application_id: ID of the application to update
        new_status: The target status
        session: Database session
        admin_notes: Optional notes from the admin

    Returns:
        Tuple of (updated ApplicationRead, list of email payload dicts).
        Each payload dict has keys: ``to``, ``subject``, ``body``.

    Raises:
        ApplicationNotFoundError: If application not found
        InvalidApplicationStatusTransitionError: If the status transition is not allowed
    """
    result = await session.execute(
        select(Application).where(Application.id == application_id)  # pyright: ignore[reportArgumentType]
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )

    # Validate transition
    allowed = VALID_TRANSITIONS.get(application.status, set())
    if new_status not in allowed:
        raise InvalidApplicationStatusTransitionError(
            f"Cannot transition application from {application.status} to {new_status}"
        )

    old_status = application.status
    application.status = new_status
    if admin_notes is not None:
        application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()

    # Fetch related records needed for email content
    candidate_result = await session.execute(
        select(CandidateProfile).where(CandidateProfile.id == application.candidate_id)  # pyright: ignore[reportArgumentType]
    )
    candidate = candidate_result.scalar_one()

    job_result = await session.execute(
        select(Job).where(Job.id == application.job_id)  # pyright: ignore[reportArgumentType]
    )
    job = job_result.scalar_one()

    company_result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == job.company_id)  # pyright: ignore[reportArgumentType]
    )
    company = company_result.scalar_one()

    user_result = await session.execute(
        select(User).where(User.id == company.user_id)  # pyright: ignore[reportArgumentType]
    )
    company_user = user_result.scalar_one()

    from src.templates.email import (
        build_application_status_candidate_html,
        build_application_status_company_html,
    )

    _STATUS_HE = {
        "NEW": "חדש",
        "APPROVED_BY_ADMIN": "אושר על-ידי מנהל",
        "REJECTED": "נדחה",
        "HIRED": "התקבל לעבודה",
    }
    new_status_he = _STATUS_HE.get(str(new_status), str(new_status))
    old_status_he = _STATUS_HE.get(str(old_status), str(old_status))

    email_payloads: list[dict] = [
        {
            "to": candidate.email,
            "subject": f"עדכון סטטוס מועמדות למשרת '{job.title}'",
            "body": (
                f"שלום {candidate.full_name},\n"
                f"סטטוס מועמדותך למשרת '{job.title}' עודכן ל-{new_status_he}."
            ),
            "html_body": build_application_status_candidate_html(
                candidate_name=candidate.full_name,
                job_title=job.title,
                old_status=old_status_he,
                new_status=new_status_he,
                notes=admin_notes,
            ),
        },
        {
            "to": company_user.email,
            "subject": f"עדכון סטטוס מועמדות למשרת '{job.title}'",
            "body": (
                f"שלום {company.name},\n"
                f"סטטוס מועמדות למשרת '{job.title}' עודכן ל-{new_status_he}."
            ),
            "html_body": build_application_status_company_html(
                company_name=company.name or "",
                job_title=job.title,
                candidate_name=candidate.full_name,
                old_status=old_status_he,
                new_status=new_status_he,
                notes=admin_notes,
            ),
        },
    ]

    return ApplicationRead.model_validate(application), email_payloads


async def delete_application(
    application_id: int,
    session: AsyncSession,
) -> None:
    """Delete an application record.

    Removes the job ↔ candidate link. The candidate profile is preserved.

    Raises:
        ApplicationNotFoundError: If application not found
    """
    application = await session.get(Application, application_id)
    if application is None:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )
    await session.delete(application)
    await session.commit()
