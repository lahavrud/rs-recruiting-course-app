"""Unit tests for admin application management service functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import ApplicationRead, ApplicationWithDetails
from src.services.applications_admin import (
    get_application,
    list_applications,
    update_application_status,
)
from src.services.exceptions import (
    ApplicationNotFoundError,
    InvalidApplicationStatusTransitionError,
)

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
    """Returns empty list when no applications exist."""
    result = await list_applications(session)
    assert result == []


@pytest.mark.asyncio
async def test_list_applications_returns_with_details(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Returns ApplicationWithDetails instances."""
    candidate = await _make_candidate(session)
    await _make_application(session, company_with_user, candidate)

    results = await list_applications(session)

    assert len(results) == 1
    assert isinstance(results[0], ApplicationWithDetails)
    assert results[0].job is not None
    assert results[0].candidate is not None


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

    new_results = await list_applications(session, status=ApplicationStatus.NEW)
    approved_results = await list_applications(
        session, status=ApplicationStatus.APPROVED_BY_ADMIN
    )

    assert len(new_results) == 1
    assert new_results[0].status == ApplicationStatus.NEW
    assert len(approved_results) == 1
    assert approved_results[0].status == ApplicationStatus.APPROVED_BY_ADMIN


@pytest.mark.asyncio
async def test_list_applications_filter_by_job_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by job_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    results = await list_applications(session, job_id=app1.job_id)

    assert len(results) == 1
    assert results[0].job_id == app1.job_id


@pytest.mark.asyncio
async def test_list_applications_filter_by_candidate_id(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """Filters correctly by candidate_id."""
    c1 = await _make_candidate(session, email="c1@test.com")
    c2 = await _make_candidate(session, email="c2@test.com")
    app1 = await _make_application(session, company_with_user, c1)
    await _make_application(session, company_with_user, c2)

    results = await list_applications(session, candidate_id=c1.id)

    assert len(results) == 1
    assert results[0].candidate_id == app1.candidate_id


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
    assert len(email_payloads) == 2


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
async def test_update_status_invalid_transition_rejected_is_terminal(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """REJECTED is a terminal state — no further transitions allowed."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.REJECTED
    )

    with pytest.raises(InvalidApplicationStatusTransitionError):
        await update_application_status(
            app.id, ApplicationStatus.APPROVED_BY_ADMIN, session
        )


@pytest.mark.asyncio
async def test_update_status_invalid_transition_hired_is_terminal(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """HIRED is a terminal state — no further transitions allowed."""
    candidate = await _make_candidate(session)
    app = await _make_application(
        session, company_with_user, candidate, status=ApplicationStatus.HIRED
    )

    with pytest.raises(InvalidApplicationStatusTransitionError):
        await update_application_status(app.id, ApplicationStatus.REJECTED, session)


@pytest.mark.asyncio
async def test_update_status_invalid_transition_new_to_hired(
    session: AsyncSession, company_with_user: CompanyProfile
):
    """NEW → HIRED skips APPROVED_BY_ADMIN and is not allowed."""
    candidate = await _make_candidate(session)
    app = await _make_application(session, company_with_user, candidate)

    with pytest.raises(InvalidApplicationStatusTransitionError):
        await update_application_status(app.id, ApplicationStatus.HIRED, session)


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
    # Notes are now in the html_body (HTML template), not the plain text body
    assert any("Strong candidate" in p.get("html_body", "") for p in email_payloads)


@pytest.mark.asyncio
async def test_update_status_not_found(session: AsyncSession):
    """Raises ApplicationNotFoundError for a non-existent ID."""
    with pytest.raises(ApplicationNotFoundError):
        await update_application_status(
            99999, ApplicationStatus.APPROVED_BY_ADMIN, session
        )
