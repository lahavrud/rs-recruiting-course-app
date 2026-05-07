"""Unit tests for admin application management service functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import ApplicationRead, ApplicationWithDetails
from src.services.applications_admin import (
    get_application,
    list_applications,
    update_application_notes,
    update_application_status,
)
from src.services.exceptions import ApplicationNotFoundError

# ==================== Helpers ====================


async def _make_application(
    session: AsyncSession,
    company: CompanyProfile,
    candidate: CandidateProfile,
    status: ApplicationStatus = ApplicationStatus.NEW,
    job_status: JobStatus = JobStatus.PUBLISHED,
) -> Application:
    """Helper to create a job + application in the given session."""
    job = Job(
        company_id=company.id,
        title="Test Job",
        description="Description",
        requirements="Requirements",
        location="Location",
        status=job_status,
    )
    session.add(job)
    await session.flush()

    application = Application(
        job_id=job.id,
        candidate_id=candidate.id,
        status=status,
    )
    session.add(application)
    await session.commit()
    await session.refresh(application)
    return application


async def _make_candidate(
    session: AsyncSession, email: str = "c@test.com"
) -> CandidateProfile:
    """Helper to create a candidate in the given session."""
    candidate = CandidateProfile(full_name="Test Candidate", email=email)
    session.add(candidate)
    await session.flush()
    return candidate


# ==================== list_applications ====================


@pytest.mark.asyncio
async def test_list_applications_empty(session: AsyncSession):
    """Returns an empty page envelope when no applications exist."""
    page = await list_applications(session)
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_applications_returns_with_details(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns ApplicationWithDetails instances inside the page envelope."""
    candidate = await _make_candidate(session)
    await _make_application(session, company_with_user, candidate)

    page = await list_applications(session)

    assert len(page.items) == 1
    assert isinstance(page.items[0], ApplicationWithDetails)
    assert page.items[0].job is not None
    assert page.items[0].candidate is not None
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_applications_filter_by_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by application status."""
    candidate = await _make_candidate(session)
    await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.NEW
    )
    c2 = await _make_candidate(session, email="c2@test.com")
    await _make_application(
        session, company_with_user, c2, status=ApplicationStatus.APPROVED_BY_ADMIN
    )

    new_page = await list_applications(session, status=ApplicationStatus.NEW)
    approved_page = await list_applications(
        session, status=ApplicationStatus.APPROVED_BY_ADMIN
    )

    assert len(new_page.items) == 1
    assert new_page.items[0].status == ApplicationStatus.NEW
    assert len(approved_page.items) == 1
    assert approved_page.items[0].status == ApplicationStatus.APPROVED_BY_ADMIN


@pytest.mark.asyncio
async def test_list_applications_filter_by_job_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by job_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, job_id=app1.job_id)

    assert len(page.items) == 1
    assert page.items[0].job_id == app1.job_id


@pytest.mark.asyncio
async def test_list_applications_filter_by_candidate_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by candidate_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    page = await list_applications(session, candidate_id=c1.id)

    assert len(page.items) == 1
    assert page.items[0].candidate_id == app1.candidate_id


# ==================== get_application ====================


@pytest.mark.asyncio
async def test_get_application_success(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns ApplicationWithDetails for a valid ID."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result = await get_application(app.id, session)

    assert isinstance(result, ApplicationWithDetails)
    assert result.id == app.id
    assert result.job is not None
    assert result.candidate is not None
    assert result.candidate.email == candidate.email


@pytest.mark.asyncio
async def test_get_application_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError, match="99999"):
        await get_application(99999, session)


# ==================== update_application_status ====================


@pytest.mark.asyncio
async def test_update_status_new_to_approved(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NEW → APPROVED_BY_ADMIN is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, email_payloads = await update_application_status(
        app.id, ApplicationStatus.APPROVED_BY_ADMIN, session
    )

    assert isinstance(result, ApplicationRead)
    assert result.status == ApplicationStatus.APPROVED_BY_ADMIN
    assert email_payloads == []


@pytest.mark.asyncio
async def test_update_status_new_to_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NEW → REJECTED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_approved_to_hired(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """APPROVED_BY_ADMIN → HIRED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session,
        company_with_user,
        candidate,
        status=ApplicationStatus.APPROVED_BY_ADMIN,
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.HIRED, session
    )

    assert result.status == ApplicationStatus.HIRED


@pytest.mark.asyncio
async def test_update_status_approved_to_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """APPROVED_BY_ADMIN → REJECTED is a valid transition."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session,
        company_with_user,
        candidate,
        status=ApplicationStatus.APPROVED_BY_ADMIN,
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )

    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_revert_from_rejected(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can revert a REJECTED application — mis-click recovery."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.REJECTED
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.APPROVED_BY_ADMIN, session
    )
    assert result.status == ApplicationStatus.APPROVED_BY_ADMIN


@pytest.mark.asyncio
async def test_update_status_revert_from_hired(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can revert a HIRED application — mis-click recovery."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.HIRED
    )

    result, _ = await update_application_status(
        app.id, ApplicationStatus.REJECTED, session
    )
    assert result.status == ApplicationStatus.REJECTED


@pytest.mark.asyncio
async def test_update_status_skips_intermediate_steps(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin can fast-forward NEW → HIRED in one step."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, _ = await update_application_status(
        app.id, ApplicationStatus.HIRED, session
    )
    assert result.status == ApplicationStatus.HIRED


@pytest.mark.asyncio
async def test_update_status_with_admin_notes(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Admin notes are persisted on status update."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result, email_payloads = await update_application_status(
        app.id,
        ApplicationStatus.APPROVED_BY_ADMIN,
        session,
        admin_notes="Strong candidate, schedule interview",
    )

    assert result.admin_notes == "Strong candidate, schedule interview"
    assert email_payloads == []


@pytest.mark.asyncio
async def test_update_status_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError):
        await update_application_status(
            99999, ApplicationStatus.APPROVED_BY_ADMIN, session
        )


# ==================== update_application_notes ====================


@pytest.mark.asyncio
async def test_update_application_notes_persists_text(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """update_application_notes overwrites admin_notes without changing status."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    result = await update_application_notes(
        app.id, "Looks promising — schedule call.", session
    )
    await session.commit()

    assert isinstance(result, ApplicationRead)
    assert result.admin_notes == "Looks promising — schedule call."
    assert result.status == ApplicationStatus.NEW  # untouched


@pytest.mark.asyncio
async def test_update_application_notes_clears_to_none(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Passing None clears the notes field."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    await update_application_notes(app.id, "first pass", session)
    await session.commit()
    cleared = await update_application_notes(app.id, None, session)
    await session.commit()
    assert cleared.admin_notes is None


@pytest.mark.asyncio
async def test_update_application_notes_not_found(session: AsyncSession):
    with pytest.raises(ApplicationNotFoundError):
        await update_application_notes(99999, "x", session)
