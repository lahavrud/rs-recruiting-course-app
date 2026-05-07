"""Admin service functions for application (match) management."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.enums import ApplicationStatus
from src.models import Application
from src.schemas import ApplicationRead, ApplicationWithDetails
from src.services.exceptions import ApplicationNotFoundError


async def list_applications(
    session: AsyncSession,
    *,
    status: ApplicationStatus | None = None,
    job_id: int | None = None,
    candidate_id: int | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[ApplicationWithDetails]:
    """One page of applications with optional filters, newest first."""
    page_size = clamp_limit(limit)
    base = select(Application).options(
        selectinload(Application.job),  # pyright: ignore[reportArgumentType]
        selectinload(Application.candidate),  # pyright: ignore[reportArgumentType]
    )
    if status is not None:
        base = base.where(Application.status == status)  # pyright: ignore[reportArgumentType]
    if job_id is not None:
        base = base.where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    if candidate_id is not None:
        base = base.where(Application.candidate_id == candidate_id)  # pyright: ignore[reportArgumentType]

    query = apply_cursor(
        base,
        sort_col=Application.created_at,  # pyright: ignore[reportArgumentType]
        id_col=Application.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=ApplicationWithDetails.model_validate,
        cursor_key=lambda a: (a.created_at, a.id),
        limit=page_size,
    )


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
    """
    result = await session.execute(
        select(Application).where(Application.id == application_id)  # pyright: ignore[reportArgumentType]
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )

    # Admin can move to any status — including reverting from terminal states
    # for mis-click recovery.
    application.status = new_status
    if admin_notes is not None:
        application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()

    return ApplicationRead.model_validate(application), []


async def update_application_notes(
    application_id: int,
    admin_notes: str | None,
    session: AsyncSession,
) -> ApplicationRead:
    """Update only the admin_notes field on an application.

    Does not change status and does not enqueue any emails.

    Raises:
        ApplicationNotFoundError: If application not found.
    """
    result = await session.execute(
        select(Application).where(Application.id == application_id)  # pyright: ignore[reportArgumentType]
    )
    application = result.scalar_one_or_none()
    if not application:
        raise ApplicationNotFoundError(
            f"Application with ID {application_id} not found"
        )

    application.admin_notes = admin_notes
    application.updated_at = datetime.now(timezone.utc)
    await session.flush()
    await session.refresh(application)
    return ApplicationRead.model_validate(application)


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
