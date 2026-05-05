"""Unit tests for candidate service layer."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, Job
from src.schemas import CandidateProfileCreate
from src.services.candidates import (
    create_candidate_profile,
    find_candidate_by_email,
    update_candidate_profile,
)
from src.services.exceptions import ApplicationAlreadyExistsError, JobNotFoundError

_PDF_BYTES = b"%PDF-1.4" + b"\x00" * 50


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_success(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test successfully creating a candidate profile without resume."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate data
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="123-456-7890",
        linkedin_url="https://linkedin.com/in/johndoe",
        service_concept="I want to work on exciting projects",
        salary_expectations="100k-120k",
    )

    candidate = await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=job.id,
        session=session,
    )

    assert candidate.id is not None
    assert candidate.full_name == "John Doe"
    assert candidate.email == "john@example.com"
    assert candidate.phone == "123-456-7890"
    assert candidate.linkedin_url == "https://linkedin.com/in/johndoe"
    assert candidate.resume_path is None

    # Verify Application was created
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate.id,  # pyright: ignore[reportArgumentType]
            Application.job_id == job.id,  # pyright: ignore[reportArgumentType]
        )
    )
    application = result.scalar_one_or_none()
    assert application is not None
    assert application.status == ApplicationStatus.NEW

    # Note: Email is only sent if admin users exist
    # This test doesn't create an admin, so email won't be sent
    # For email testing, see test_create_candidate_profile_sends_admin_email


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_with_resume(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test creating a candidate profile with resume file upload."""
    mock_enqueue_email.return_value = "test-job-id"

    # Mock storage provider
    mock_storage = AsyncMock()
    mock_storage.upload_file = AsyncMock(return_value="resume-uuid-123.pdf")
    mock_storage_provider.return_value = mock_storage

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate data with resume
    candidate_data = CandidateProfileCreate(
        full_name="Jane Doe",
        email="jane@example.com",
        phone="987-654-3210",
    )

    resume_file = _PDF_BYTES
    resume_filename = "resume.pdf"

    candidate = await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=job.id,
        resume_file=resume_file,
        resume_filename=resume_filename,
        session=session,
    )

    assert candidate.id is not None
    assert candidate.full_name == "Jane Doe"
    assert candidate.email == "jane@example.com"
    assert candidate.resume_path == "resume-uuid-123.pdf"

    # Verify storage was called
    mock_storage.upload_file.assert_called_once()
    call_args = mock_storage.upload_file.call_args
    assert call_args[1]["file_content"] == resume_file
    assert call_args[1]["file_name"] == resume_filename

    # Verify Application was created
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate.id,  # pyright: ignore[reportArgumentType]
            Application.job_id == job.id,  # pyright: ignore[reportArgumentType]
        )
    )
    application = result.scalar_one_or_none()
    assert application is not None
    assert application.status == ApplicationStatus.NEW


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_duplicate_email(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test duplicate email reuses existing profile."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create two published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Junior Python Developer",
        description="We are looking for a junior Python developer...",
        requirements="1+ years experience with Python",
        location="Tel Aviv, Israel",
    )
    session.add(job1)
    session.add(job2)
    await session.commit()
    await session.refresh(job1)
    await session.refresh(job2)
    assert job1.id is not None
    assert job2.id is not None

    # Create first candidate for job1
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job1.id,
        session=session,
    )
    assert candidate1.id is not None
    candidate_id = candidate1.id

    # Create second application with same email for job2
    # Should reuse existing profile and create new Application
    candidate_data2 = CandidateProfileCreate(
        full_name="John Smith",  # Different name (should be updated)
        email="john@example.com",  # Same email
        phone="050-000-0001",
    )
    candidate2 = await create_candidate_profile(
        candidate_data=candidate_data2,
        job_id=job2.id,
        session=session,
    )

    # Verify: Same candidate profile ID, name updated
    assert candidate2.id == candidate_id
    assert candidate2.full_name == "John Smith"  # Name should be updated

    # Verify: Two applications exist
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        )
    )
    applications = result.scalars().all()
    assert len(applications) == 2
    job_ids = {app.job_id for app in applications}
    assert job_ids == {job1.id, job2.id}


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_invalid_file(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test creating a candidate profile with invalid file type."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate data with invalid file type
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    resume_file = b"fake content"
    resume_filename = "resume.txt"  # Invalid file type

    with pytest.raises(ValueError, match="Invalid file type"):
        await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=job.id,
            resume_file=resume_file,
            resume_filename=resume_filename,
            session=session,
        )


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_forged_magic_bytes_rejected(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that a file with a forged extension is rejected via magic byte check."""
    mock_enqueue_email.return_value = "test-job-id"
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="Description",
        requirements="Requirements",
        location="Tel Aviv",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="forged@example.com",
        phone="050-000-0001",
    )
    exe_bytes = b"MZ" + b"\x00" * 100  # Windows PE disguised as PDF
    with pytest.raises(ValueError, match="does not match"):
        await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=job.id,
            resume_file=exe_bytes,
            resume_filename="resume.pdf",
            session=session,
        )


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_file_size_limit(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test creating a candidate profile with file exceeding size limit."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate data with oversized file
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    # Create file larger than 10MB
    resume_file = b"x" * (11 * 1024 * 1024)  # 11MB
    resume_filename = "resume.pdf"

    with pytest.raises(ValueError, match="File size exceeds maximum"):
        await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=job.id,
            resume_file=resume_file,
            resume_filename=resume_filename,
            session=session,
        )


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_application_on_profile_creation(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that Application record is created when candidate profile is created."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    candidate = await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=job.id,
        session=session,
    )

    # Verify Application was created with correct status
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate.id,  # pyright: ignore[reportArgumentType]
            Application.job_id == job.id,  # pyright: ignore[reportArgumentType]
        )
    )
    application = result.scalar_one()
    assert application.status == ApplicationStatus.NEW
    assert application.candidate_id == candidate.id
    assert application.job_id == job.id


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_sends_admin_email(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that email notification is sent to admins when candidate applies."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create admin user
    from src.core.infrastructure.security import get_password_hash
    from src.enums import UserRole
    from src.models import User

    admin = User(
        email="admin@test.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(admin)
    await session.commit()

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="123-456-7890",
    )

    await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=job.id,
        session=session,
    )

    # Verify email was sent
    mock_enqueue_email.assert_called_once()
    call_args = mock_enqueue_email.call_args
    # Function is called with keyword arguments
    assert call_args.kwargs["to"] == ["admin@test.com"]  # Admin email
    assert "New Application" in call_args.kwargs["subject"]  # Subject
    assert "John Doe" in call_args.kwargs["body"]  # Body contains candidate name
    assert (
        "Senior Python Developer" in call_args.kwargs["body"]
    )  # Body contains job title


@pytest.mark.asyncio
async def test_create_candidate_profile_job_not_found(session: AsyncSession):
    """Test creating a candidate profile for non-existent job."""
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    with pytest.raises(JobNotFoundError, match="Job with ID 999 not found"):
        await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=999,  # Non-existent job ID
            session=session,
        )


@pytest.mark.asyncio
async def test_create_candidate_profile_session_required():
    """Test that create_candidate_profile requires a session."""
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    with pytest.raises(ValueError, match="Database session is required"):
        await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=1,
            session=None,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_reuses_existing_profile(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that applying to different jobs with same email reuses existing profile."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create two published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Junior Python Developer",
        description="We are looking for a junior Python developer...",
        requirements="1+ years experience with Python",
        location="Tel Aviv, Israel",
    )
    session.add(job1)
    session.add(job2)
    await session.commit()
    await session.refresh(job1)
    await session.refresh(job2)
    assert job1.id is not None
    assert job2.id is not None

    # Create candidate with email "john@example.com" for Job A
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job1.id,
        session=session,
    )
    candidate_id = candidate1.id
    assert candidate_id is not None

    # Create another application with same email for Job B
    candidate_data2 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate2 = await create_candidate_profile(
        candidate_data=candidate_data2,
        job_id=job2.id,
        session=session,
    )

    # Verify: Same candidate profile ID, two applications exist
    assert candidate2.id == candidate_id

    # Verify two applications exist
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        )
    )
    applications = result.scalars().all()
    assert len(applications) == 2
    job_ids = {app.job_id for app in applications}
    assert job_ids == {job1.id, job2.id}


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_updates_existing_profile(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that applying again with same email updates profile with new data."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create two published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Junior Python Developer",
        description="We are looking for a junior Python developer...",
        requirements="1+ years experience with Python",
        location="Tel Aviv, Israel",
    )
    session.add(job1)
    session.add(job2)
    await session.commit()
    await session.refresh(job1)
    await session.refresh(job2)
    assert job1.id is not None
    assert job2.id is not None

    # Create candidate with phone but no linkedin
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job1.id,
        session=session,
    )
    candidate_id = candidate1.id
    assert candidate_id is not None
    assert candidate1.phone == "050-000-0001"
    assert candidate1.linkedin_url is None

    # Create second application with same email, adding linkedin
    candidate_data2 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
        linkedin_url="https://linkedin.com/in/johndoe",
    )
    candidate2 = await create_candidate_profile(
        candidate_data=candidate_data2,
        job_id=job2.id,
        session=session,
    )

    # Verify: linkedin filled in on second application, same profile ID
    assert candidate2.id == candidate_id
    assert candidate2.phone == "050-000-0001"
    assert candidate2.linkedin_url == "https://linkedin.com/in/johndoe"


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
@patch("src.services.candidates.get_storage_provider")
async def test_create_candidate_profile_does_not_overwrite_resume(
    mock_storage_provider,
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that applying again with new resume doesn't overwrite existing resume."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create two published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Junior Python Developer",
        description="We are looking for a junior Python developer...",
        requirements="1+ years experience with Python",
        location="Tel Aviv, Israel",
    )
    session.add(job1)
    session.add(job2)
    await session.commit()
    await session.refresh(job1)
    await session.refresh(job2)
    assert job1.id is not None
    assert job2.id is not None

    # Mock storage provider
    mock_storage = AsyncMock()
    mock_storage.upload_file = AsyncMock(return_value="resume1.pdf")
    mock_storage_provider.return_value = mock_storage

    # Create candidate with resume_path = "resume1.pdf"
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    resume_file1 = _PDF_BYTES
    resume_filename1 = "resume1.pdf"

    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job1.id,
        resume_file=resume_file1,
        resume_filename=resume_filename1,
        session=session,
    )
    candidate_id = candidate1.id
    assert candidate_id is not None
    assert candidate1.resume_path == "resume1.pdf"

    # Create second application with same email, new resume = "resume2.pdf"
    mock_storage.upload_file = AsyncMock(return_value="resume2.pdf")
    candidate_data2 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    resume_file2 = _PDF_BYTES
    resume_filename2 = "resume2.pdf"

    candidate2 = await create_candidate_profile(
        candidate_data=candidate_data2,
        job_id=job2.id,
        resume_file=resume_file2,
        resume_filename=resume_filename2,
        session=session,
    )

    # Verify: Profile keeps original resume_path (don't overwrite existing resume)
    assert candidate2.id == candidate_id
    assert candidate2.resume_path == "resume1.pdf"  # Original resume kept


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_always_updates_full_name(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that full_name is always updated even if candidate exists."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create two published jobs
    job1 = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    job2 = Job(
        company_id=company_with_user.id,
        title="Junior Python Developer",
        description="We are looking for a junior Python developer...",
        requirements="1+ years experience with Python",
        location="Tel Aviv, Israel",
    )
    session.add(job1)
    session.add(job2)
    await session.commit()
    await session.refresh(job1)
    await session.refresh(job2)
    assert job1.id is not None
    assert job2.id is not None

    # Create candidate with full_name = "John Doe"
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job1.id,
        session=session,
    )
    candidate_id = candidate1.id
    assert candidate_id is not None
    assert candidate1.full_name == "John Doe"

    # Create second application with same email, full_name = "John Smith"
    candidate_data2 = CandidateProfileCreate(
        full_name="John Smith",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate2 = await create_candidate_profile(
        candidate_data=candidate_data2,
        job_id=job2.id,
        session=session,
    )

    # Verify: Profile updated with "John Smith"
    assert candidate2.id == candidate_id
    assert candidate2.full_name == "John Smith"


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_create_candidate_profile_duplicate_application_raises_error(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that applying twice to same job raises ApplicationAlreadyExistsError."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a published job
    job = Job(
        company_id=company_with_user.id,
        title="Senior Python Developer",
        description="We are looking for a senior Python developer...",
        requirements="5+ years experience with Python, FastAPI, PostgreSQL",
        location="Tel Aviv, Israel",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    assert job.id is not None

    # Create candidate application for Job A
    candidate_data1 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate1 = await create_candidate_profile(
        candidate_data=candidate_data1,
        job_id=job.id,
        session=session,
    )
    candidate_id = candidate1.id
    assert candidate_id is not None

    # Try to create another application for same Job A with same email
    candidate_data2 = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )

    # Verify: Raises ApplicationAlreadyExistsError
    with pytest.raises(ApplicationAlreadyExistsError) as exc_info:
        await create_candidate_profile(
            candidate_data=candidate_data2,
            job_id=job.id,
            session=session,
        )
    assert exc_info.value.job_id == job.id
    assert exc_info.value.candidate_id == candidate_id


@pytest.mark.asyncio
async def test_find_candidate_by_email_exists(
    session: AsyncSession,
    company_with_user,
):
    """Test find_candidate_by_email when candidate exists."""
    # Create a candidate
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@example.com",
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    assert candidate.id is not None

    # Call find_candidate_by_email()
    found = await find_candidate_by_email(email="john@example.com", session=session)

    # Verify: Returns correct candidate
    assert found is not None
    assert found.id == candidate.id
    assert found.email == "john@example.com"


@pytest.mark.asyncio
async def test_find_candidate_by_email_not_exists(session: AsyncSession):
    """Test find_candidate_by_email when candidate doesn't exist."""
    # Call find_candidate_by_email() with non-existent email
    found = await find_candidate_by_email(
        email="nonexistent@example.com", session=session
    )

    # Verify: Returns None
    assert found is None


@pytest.mark.asyncio
async def test_update_candidate_profile(
    session: AsyncSession,
):
    """Test update_candidate_profile helper function."""
    # Create existing candidate with minimal data
    candidate = CandidateProfile(
        full_name="John Doe",
        email="john@example.com",
        phone=None,
        linkedin_url=None,
    )
    session.add(candidate)
    await session.commit()
    await session.refresh(candidate)
    assert candidate.id is not None

    # Update with new data
    candidate_data = CandidateProfileCreate(
        full_name="John Smith",  # Should be updated
        email="john@example.com",
        phone="123-456-7890",  # Should be updated (was None)
        linkedin_url="https://linkedin.com/in/johndoe",  # Should be updated (was None)
    )

    updated = await update_candidate_profile(
        candidate=candidate,
        candidate_data=candidate_data,
        session=session,
    )

    # Verify updates
    assert updated.full_name == "John Smith"
    assert updated.phone == "123-456-7890"
    assert updated.linkedin_url == "https://linkedin.com/in/johndoe"
    assert updated.email == "john@example.com"  # Email should not change


@pytest.mark.asyncio
@patch("src.services.candidates.enqueue_email_task")
async def test_one_profile_can_have_many_applications(
    mock_enqueue_email,
    session: AsyncSession,
    company_with_user,
):
    """Test that one candidate profile can have many different applications."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create 5 different jobs
    jobs = []
    for i in range(5):
        job = Job(
            company_id=company_with_user.id,
            title=f"Job {i + 1}",
            description=f"Description for job {i + 1}",
            requirements=f"Requirements for job {i + 1}",
            location="Tel Aviv, Israel",
        )
        session.add(job)
        jobs.append(job)
    await session.commit()
    for job in jobs:
        await session.refresh(job)
        assert job.id is not None

    # Create first application
    candidate_data = CandidateProfileCreate(
        full_name="John Doe",
        email="john@example.com",
        phone="050-000-0001",
    )
    candidate = await create_candidate_profile(
        candidate_data=candidate_data,
        job_id=jobs[0].id,
        session=session,
    )
    candidate_id = candidate.id
    assert candidate_id is not None

    # Apply to remaining 4 jobs with same email
    for i in range(1, 5):
        candidate = await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=jobs[i].id,
            session=session,
        )
        # Verify same profile is reused
        assert candidate.id == candidate_id

    # Verify: One profile has 5 applications
    result = await session.execute(
        select(Application).where(  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        )
    )
    applications = result.scalars().all()
    assert len(applications) == 5

    # Verify all job IDs are different
    job_ids = {app.job_id for app in applications}
    assert len(job_ids) == 5
    assert job_ids == {job.id for job in jobs}
