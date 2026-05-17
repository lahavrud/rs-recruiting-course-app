"""Tests for candidate application endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import and_, select

from src.enums import ApplicationStatus
from src.models import Application, AuditLog, CandidateProfile, Job
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_success(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test successfully submitting an application via API."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-123-4567",
        "linkedin_url": "https://linkedin.com/in/johndoe",
        "service_concept": "I want to work on exciting projects",
        "salary_expectations": "100k-120k",
        "strength": "Problem solving",
        "growth_area": "Public speaking",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "John Doe"
    assert data["email"] == "john@example.com"
    assert data["phone"] == "050-123-4567"
    assert data["id"] is not None

    # Verify candidate was created in database with consent
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CandidateProfile).where(
                CandidateProfile.email == "john@example.com"  # pyright: ignore[reportArgumentType]
            )
        )
        candidate = result.scalar_one_or_none()
        assert candidate is not None
        assert candidate.full_name == "John Doe"
        assert candidate.consent_given_at is not None
        assert candidate.consent_policy_version == "1.1"

        # Verify Application was created with interview fields
        result = await session.execute(
            select(Application).where(
                and_(
                    Application.candidate_id == candidate.id,  # pyright: ignore[reportArgumentType]
                    Application.job_id == published_job.id,  # pyright: ignore[reportArgumentType]
                )
            )
        )
        application = result.scalar_one_or_none()
        assert application is not None
        assert application.status == ApplicationStatus.NEW
        assert application.service_concept == "I want to work on exciting projects"
        assert application.salary_expectations == "100k-120k"
        assert application.strength == "Problem solving"
        assert application.growth_area == "Public speaking"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
@patch("src.services.public.applications.get_storage_provider")
async def test_apply_endpoint_with_resume(
    mock_storage_provider,
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test submitting an application with resume file upload."""
    mock_enqueue_email.return_value = "test-job-id"

    # Mock storage provider
    mock_storage = AsyncMock()
    mock_storage.upload_file = AsyncMock(return_value="resume-uuid-123.pdf")
    mock_storage_provider.return_value = mock_storage

    form_data = {
        "job_id": published_job.id,
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "050-987-6543",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    files = {"resume": ("resume.pdf", b"%PDF-1.4\x00" * 5, "application/pdf")}

    response = await public_client.post(
        "/api/candidates/apply",
        data=form_data,
        files=files,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Jane Doe"
    assert data["email"] == "jane@example.com"
    assert data["resume_path"] == "resume-uuid-123.pdf"

    # Verify storage was called
    mock_storage.upload_file.assert_called_once()


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_validation_error(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test submitting an application with validation errors."""
    mock_enqueue_email.return_value = "test-job-id"

    # Missing required fields
    form_data = {
        "job_id": published_job.id,
        # Missing full_name and email
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
@patch("src.services.public.applications.get_storage_provider")
async def test_apply_endpoint_invalid_file_type(
    mock_storage_provider,
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test submitting an application with invalid file type."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0001",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    files = {
        "resume": ("resume.txt", b"fake content", "text/plain")  # Invalid file type
    }

    response = await public_client.post(
        "/api/candidates/apply",
        data=form_data,
        files=files,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_application"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
@patch("src.services.public.applications.get_storage_provider")
async def test_apply_endpoint_file_size_limit(
    mock_storage_provider,
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test submitting an application with file exceeding size limit."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0002",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    # Create file larger than 10MB
    large_file_content = b"x" * (11 * 1024 * 1024)  # 11MB
    files = {"resume": ("resume.pdf", large_file_content, "application/pdf")}

    response = await public_client.post(
        "/api/candidates/apply",
        data=form_data,
        files=files,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_application"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_creates_application(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that Application record is created when submitting via API."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0003",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 201
    data = response.json()
    candidate_id = data["id"]

    # Verify Application was created
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(Application).where(
                and_(
                    Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
                    Application.job_id == published_job.id,  # pyright: ignore[reportArgumentType]
                )
            )
        )
        application = result.scalar_one_or_none()
        assert application is not None
        assert application.status == ApplicationStatus.NEW


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_job_not_found(
    mock_enqueue_email,
    public_client: AsyncClient,
):
    """Test submitting an application for non-existent job."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": 999,  # Non-existent job ID
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0004",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 404
    assert "Job with ID 999 not found" in response.json()["detail"]


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_public_access(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that apply endpoint is publicly accessible (no auth required)."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0005",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    # Should work without authentication
    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "John Doe"
    assert data["email"] == "john@example.com"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_reuses_existing_profile(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that API endpoint correctly handles duplicate email scenario."""
    mock_enqueue_email.return_value = "test-job-id"

    # Create a second job
    from src.models import CompanyProfile
    from tests.conftest import TestSessionLocal

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(
                CompanyProfile.id == published_job.company_id  # pyright: ignore[reportArgumentType]
            )
        )
        company = result.scalar_one()
        assert company.id is not None

        job2 = Job(
            company_id=company.id,  # type: ignore[arg-type]
            title="Junior Python Developer",
            short_description="Short blurb for testing.",
            description="We are looking for a junior Python developer...",
            requirements=[
                {"text": "1+ years experience with Python"},
                {"text": "Req 2"},
                {"text": "Req 3"},
            ],
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job2)
        await session.commit()
        await session.refresh(job2)
        job2_id = job2.id

    # First application
    form_data1 = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0006",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    response1 = await public_client.post("/api/candidates/apply", data=form_data1)
    assert response1.status_code == 201
    data1 = response1.json()
    candidate_id = data1["id"]

    # Second application with same email for different job
    form_data2 = {
        "job_id": job2_id,
        "full_name": "John Smith",  # Different name
        "email": "john@example.com",  # Same email
        "phone": "050-000-0006",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    response2 = await public_client.post("/api/candidates/apply", data=form_data2)
    assert response2.status_code == 201  # Should succeed, not error
    data2 = response2.json()

    # Verify: Same candidate profile ID, name updated
    assert data2["id"] == candidate_id
    assert data2["full_name"] == "John Smith"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_duplicate_application_conflict(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that applying twice to same job returns HTTP 409 Conflict."""
    mock_enqueue_email.return_value = "test-job-id"

    # First application
    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0007",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    response1 = await public_client.post("/api/candidates/apply", data=form_data)
    assert response1.status_code == 201

    # Try to apply again to same job with same email
    response2 = await public_client.post("/api/candidates/apply", data=form_data)

    # Verify: HTTP 409 Conflict
    assert response2.status_code == 409
    assert "Application already exists" in response2.json()["detail"]


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_requires_privacy_consent(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that submitting without privacy consent returns HTTP 400."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0008",
        "privacy_accepted": "false",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 400
    assert response.json()["detail"] == "privacy_consent_required"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_writes_consent_audit_event(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that a candidate.consent audit event is recorded on application."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "Audit Candidate",
        "email": "audit@example.com",
        "phone": "050-000-0009",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)
    assert response.status_code == 201
    candidate_id = response.json()["id"]

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "candidate.consent",  # pyright: ignore[reportArgumentType]
                AuditLog.target_type == "CandidateProfile",  # pyright: ignore[reportArgumentType]
                AuditLog.target_id == candidate_id,  # pyright: ignore[reportArgumentType]
            )
        )
        event = result.scalar_one_or_none()
        assert event is not None
        assert event.detail == "policy_version=1.1"
        assert event.actor_user_id is None


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_updates_consent_on_reapplication(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that consent fields are refreshed when an existing candidate re-applies."""
    mock_enqueue_email.return_value = "test-job-id"

    from src.models import CompanyProfile

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(
                CompanyProfile.id == published_job.company_id  # pyright: ignore[reportArgumentType]
            )
        )
        company = result.scalar_one()
        from src.models import Job as JobModel

        job2 = JobModel(
            company_id=company.id,  # type: ignore[arg-type]
            title="Second Position",
            short_description="Short blurb for reapplication test.",
            description="Second job for consent reapplication test.",
            requirements=[
                {"text": "req 1"},
                {"text": "req 2"},
                {"text": "req 3"},
            ],
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
        )
        session.add(job2)
        await session.commit()
        await session.refresh(job2)
        job2_id = job2.id

    form_data1 = {
        "job_id": published_job.id,
        "full_name": "Repeat Candidate",
        "email": "repeat@example.com",
        "phone": "050-000-0010",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    resp1 = await public_client.post("/api/candidates/apply", data=form_data1)
    assert resp1.status_code == 201
    candidate_id = resp1.json()["id"]

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CandidateProfile).where(
                CandidateProfile.id == candidate_id  # pyright: ignore[reportArgumentType]
            )
        )
        after_first = result.scalar_one()
        first_consent_at = after_first.consent_given_at

    form_data2 = {
        "job_id": job2_id,
        "full_name": "Repeat Candidate",
        "email": "repeat@example.com",
        "phone": "050-000-0010",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }
    resp2 = await public_client.post("/api/candidates/apply", data=form_data2)
    assert resp2.status_code == 201

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CandidateProfile).where(
                CandidateProfile.id == candidate_id  # pyright: ignore[reportArgumentType]
            )
        )
        after_second = result.scalar_one()
        assert after_second.consent_given_at is not None
        assert after_second.consent_policy_version == "1.1"
        # Consent timestamp must be refreshed (>= first)
        assert after_second.consent_given_at >= first_consent_at  # type: ignore[operator]

        # Two audit events — one per application
        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "candidate.consent",  # pyright: ignore[reportArgumentType]
                AuditLog.target_id == candidate_id,  # pyright: ignore[reportArgumentType]
            )
        )
        events = audit_result.scalars().all()
        assert len(events) == 2


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_requires_terms_consent(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """Test that submitting without terms-of-service consent returns HTTP 400."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "John Doe",
        "email": "john@example.com",
        "phone": "050-000-0011",
        "privacy_accepted": "true",
        "terms_accepted": "false",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)

    assert response.status_code == 400
    assert response.json()["detail"] == "terms_consent_required"


@pytest.mark.asyncio
@patch("src.services.public.applications.enqueue_email_task")
async def test_apply_endpoint_persists_tos_acceptance(
    mock_enqueue_email,
    public_client: AsyncClient,
    published_job: Job,
):
    """tos_accepted_at + tos_version + audit row are written on apply."""
    mock_enqueue_email.return_value = "test-job-id"

    form_data = {
        "job_id": published_job.id,
        "full_name": "ToS Candidate",
        "email": "tos@example.com",
        "phone": "050-000-0012",
        "privacy_accepted": "true",
        "terms_accepted": "true",
    }

    response = await public_client.post("/api/candidates/apply", data=form_data)
    assert response.status_code == 201
    candidate_id = response.json()["id"]

    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CandidateProfile).where(
                CandidateProfile.id == candidate_id  # pyright: ignore[reportArgumentType]
            )
        )
        candidate = result.scalar_one()
        assert candidate.tos_accepted_at is not None
        assert candidate.tos_version == "1.0"

        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.action == "candidate.terms_accept",  # pyright: ignore[reportArgumentType]
                AuditLog.target_type == "CandidateProfile",  # pyright: ignore[reportArgumentType]
                AuditLog.target_id == candidate_id,  # pyright: ignore[reportArgumentType]
            )
        )
        event = audit.scalar_one_or_none()
        assert event is not None
        assert event.detail == "terms_version=1.0"
