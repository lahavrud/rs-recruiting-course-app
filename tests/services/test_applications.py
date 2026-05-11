"""Unit tests for the public apply-to-job flow (src/services/applications.py)."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.transactions import transactional
from src.enums import ApplicationStatus
from src.models import Application, Job
from src.schemas import CandidateProfileCreate
from src.services.applications import create_candidate_profile
from src.services.exceptions import ApplicationAlreadyExistsError, JobNotFoundError

_PDF_BYTES = b"%PDF-1.4" + b"\x00" * 50


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_published_job(
    session: AsyncSession,
    company_with_user,
    title: str = "Senior Python Developer",
) -> Job:
    """Create + persist a published job under the test company."""
    job = Job(
        company_id=company_with_user.id,
        title=title,
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience",
        location="Tel Aviv, Israel",
        salary_min=15000,
        salary_max=25000,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None
    return job


def _default_candidate(**overrides) -> CandidateProfileCreate:
    """Build a CandidateProfileCreate with sensible defaults; overrides as kwargs."""
    base = {
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0001",
    }
    base.update(overrides)
    return CandidateProfileCreate(**base)


# ── Happy paths ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_success(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Successful apply (no resume): candidate + NEW Application row are persisted."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    candidate = await create_candidate_profile(
        candidate_data=_default_candidate(
            linkedin_url="https://linkedin.com/in/johndoe",
            service_concept="I want to work on exciting projects",
            salary_expectations="100k-120k",
        ),
        job_id=job.id,
        session=session,
    )

    assert candidate.id is not None
    assert candidate.full_name == "John Doe"
    assert candidate.linkedin_url == "https://linkedin.com/in/johndoe"
    assert candidate.resume_path is None

    application = (
        await session.execute(
            select(Application).where(  # pyright: ignore[reportArgumentType]
                Application.candidate_id == candidate.id,
                Application.job_id == job.id,
            )
        )
    ).scalar_one()
    assert application.status == ApplicationStatus.NEW


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_with_resume(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Resume file is uploaded via storage and its key lands on the profile."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_storage = AsyncMock()
    mock_storage.upload_file = AsyncMock(return_value="resume-uuid-123.pdf")
    mock_storage_provider.return_value = mock_storage

    job = await _make_published_job(session, company_with_user)

    candidate_data = _default_candidate(full_name="Jane Doe", email="jane@example.com")
    candidate = await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=job.id,
        resume_file=_PDF_BYTES,
        resume_filename="resume.pdf",
        session=session,
    )

    assert candidate.resume_path == "resume-uuid-123.pdf"
    mock_storage.upload_file.assert_called_once()
    call_kwargs = mock_storage.upload_file.call_args.kwargs
    assert call_kwargs["file_content"] == _PDF_BYTES
    assert call_kwargs["file_name"] == "resumes/resume.pdf"


# ── File-validation rejection paths ───────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_invalid_file(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """A .txt resume is rejected before any storage call."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    with pytest.raises(ValueError, match="Invalid file type"):
        await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=job.id,
            resume_file=b"fake content",
            resume_filename="resume.txt",
            session=session,
        )


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_forged_magic_bytes_rejected(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """An exe renamed to .pdf is caught by the magic-byte check."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    exe_bytes = b"MZ" + b"\x00" * 100  # Windows PE header
    with pytest.raises(ValueError, match="does not match"):
        await create_candidate_profile(
            candidate_data=_default_candidate(email="forged@example.com"),
            job_id=job.id,
            resume_file=exe_bytes,
            resume_filename="resume.pdf",
            session=session,
        )


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_file_size_limit(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """A >10 MB resume is rejected before the magic-byte check."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    with pytest.raises(ValueError, match="File size exceeds maximum"):
        await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=job.id,
            resume_file=b"x" * (11 * 1024 * 1024),
            resume_filename="resume.pdf",
            session=session,
        )


# ── Email side effects ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
async def test_create_candidate_profile_sends_candidate_confirmation_email(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """The candidate gets a Hebrew HTML confirmation email after a successful apply."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    async with transactional(session):
        await create_candidate_profile(
            candidate_data=_default_candidate(phone="123-456-7890"),
            job_id=job.id,
            session=session,
        )

    # First call is the candidate confirmation; second is the admin notification.
    candidate_call = mock_enqueue_email.call_args_list[0].kwargs
    assert candidate_call["to"] == "john@example.com"
    assert "John Doe" in candidate_call["body"]
    assert "John Doe" in candidate_call["html_body"]
    assert job.title in candidate_call["html_body"]
    assert "התקבלה" in candidate_call["subject"]


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
async def test_create_candidate_profile_admin_email_falls_back_to_all_admins(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
    monkeypatch,
):
    """When ADMIN_NOTIFICATION_EMAIL is unset, every active admin is notified."""
    from src.core.infrastructure.config import settings as runtime_settings
    from src.core.infrastructure.security import get_password_hash
    from src.enums import UserRole
    from src.models import User

    monkeypatch.setattr(runtime_settings, "admin_notification_email", None)
    mock_enqueue_email.return_value = "test-job-id"

    session.add(
        User(
            email="admin@test.com",
            hashed_password=get_password_hash("password"),
            role=UserRole.ADMIN,
            is_active=True,
        )
    )
    await session.commit()

    job = await _make_published_job(session, company_with_user)

    async with transactional(session):
        await create_candidate_profile(
            candidate_data=_default_candidate(phone="123-456-7890"),
            job_id=job.id,
            session=session,
        )

    assert mock_enqueue_email.call_count == 2  # candidate + admin
    admin_call = mock_enqueue_email.call_args_list[1].kwargs
    assert admin_call["to"] == ["admin@test.com"]
    assert "John Doe" in admin_call["html_body"]
    assert job.title in admin_call["html_body"]


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
async def test_create_candidate_profile_admin_email_uses_env_var_when_set(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
    monkeypatch,
):
    """ADMIN_NOTIFICATION_EMAIL routes the admin notification to a single recipient."""
    from src.core.infrastructure.config import settings as runtime_settings

    monkeypatch.setattr(
        runtime_settings, "admin_notification_email", "ops@rsrecruit.test"
    )
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    async with transactional(session):
        await create_candidate_profile(
            candidate_data=_default_candidate(phone="123-456-7890"),
            job_id=job.id,
            session=session,
        )

    admin_call = mock_enqueue_email.call_args_list[1].kwargs
    assert admin_call["to"] == "ops@rsrecruit.test"


# ── Argument validation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_candidate_profile_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError, match="Job with ID 999 not found"):
        await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=999,
            session=session,
        )


@pytest.mark.asyncio
async def test_create_candidate_profile_session_required():
    with pytest.raises(ValueError, match="Database session is required"):
        await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=1,
            session=None,  # type: ignore[arg-type]
        )


# ── Re-apply behavior (parametrized over field-update rules) ──────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_overrides, second_overrides, expected",
    [
        # Same data twice — verifies profile reuse + 2 applications.
        ({}, {}, {"full_name": "John Doe", "linkedin_url": None}),
        # full_name is always overwritten on re-apply.
        (
            {},
            {"full_name": "John Smith"},
            {"full_name": "John Smith", "linkedin_url": None},
        ),
        # Optional fields fill in when previously None.
        (
            {},
            {"linkedin_url": "https://linkedin.com/in/johndoe"},
            {
                "full_name": "John Doe",
                "linkedin_url": "https://linkedin.com/in/johndoe",
            },
        ),
    ],
    ids=["same-data", "name-overwrites", "linkedin-fills"],
)
@patch("src.services.applications.enqueue_email_task")
async def test_create_candidate_profile_reapply_updates_profile(
    mock_enqueue_email,
    first_overrides,
    second_overrides,
    expected,
    session: AsyncSession,
    company_with_user,
):
    """Re-applying with the same email reuses the profile + applies update rules."""
    mock_enqueue_email.return_value = "test-job-id"
    job1 = await _make_published_job(session, company_with_user, title="Senior")
    job2 = await _make_published_job(session, company_with_user, title="Junior")

    first = await create_candidate_profile(
        candidate_data=_default_candidate(**first_overrides),
        job_id=job1.id,
        session=session,
    )
    second = await create_candidate_profile(
        candidate_data=_default_candidate(**second_overrides),
        job_id=job2.id,
        session=session,
    )

    assert second.id == first.id
    for field, value in expected.items():
        assert getattr(second, field) == value

    applications = (
        (
            await session.execute(
                select(Application).where(  # pyright: ignore[reportArgumentType]
                    Application.candidate_id == first.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert {a.job_id for a in applications} == {job1.id, job2.id}


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
@patch("src.services.applications.get_storage_provider")
async def test_create_candidate_profile_does_not_overwrite_resume(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Re-applying with a new resume keeps the original resume_path on the profile."""
    mock_enqueue_email.return_value = "test-job-id"
    mock_storage = AsyncMock()
    mock_storage_provider.return_value = mock_storage

    job1 = await _make_published_job(session, company_with_user, title="Senior")
    job2 = await _make_published_job(session, company_with_user, title="Junior")

    mock_storage.upload_file = AsyncMock(return_value="resume1.pdf")
    first = await create_candidate_profile(
        candidate_data=_default_candidate(),
        job_id=job1.id,
        resume_file=_PDF_BYTES,
        resume_filename="resume1.pdf",
        session=session,
    )
    assert first.resume_path == "resume1.pdf"

    mock_storage.upload_file = AsyncMock(return_value="resume2.pdf")
    second = await create_candidate_profile(
        candidate_data=_default_candidate(),
        job_id=job2.id,
        resume_file=_PDF_BYTES,
        resume_filename="resume2.pdf",
        session=session,
    )

    assert second.id == first.id
    assert second.resume_path == "resume1.pdf"  # original kept


# ── Duplicate / fan-out invariants ────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
async def test_create_candidate_profile_duplicate_application_raises_error(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Applying twice to the same job raises ApplicationAlreadyExistsError."""
    mock_enqueue_email.return_value = "test-job-id"
    job = await _make_published_job(session, company_with_user)

    first = await create_candidate_profile(
        candidate_data=_default_candidate(),
        job_id=job.id,
        session=session,
    )

    with pytest.raises(ApplicationAlreadyExistsError) as exc_info:
        await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=job.id,
            session=session,
        )
    assert exc_info.value.job_id == job.id
    assert exc_info.value.candidate_id == first.id


@pytest.mark.asyncio
@patch("src.services.applications.enqueue_email_task")
async def test_one_profile_can_have_many_applications(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """One candidate profile can fan out into many Application rows across jobs."""
    mock_enqueue_email.return_value = "test-job-id"
    jobs = [
        await _make_published_job(session, company_with_user, title=f"Job {i + 1}")
        for i in range(5)
    ]

    for job in jobs:
        candidate = await create_candidate_profile(
            candidate_data=_default_candidate(),
            job_id=job.id,
            session=session,
        )

    applications = (
        (
            await session.execute(
                select(Application).where(  # pyright: ignore[reportArgumentType]
                    Application.candidate_id == candidate.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(applications) == 5
    assert {a.job_id for a in applications} == {job.id for job in jobs}
