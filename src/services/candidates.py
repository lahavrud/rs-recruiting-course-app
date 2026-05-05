"""Candidate service layer for public application form."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.file_validation import validate_document_magic_bytes
from src.core.services.storage import StorageProvider, get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, Job
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.admin_companies import get_all_admin_emails
from src.services.exceptions import ApplicationAlreadyExistsError, JobNotFoundError


async def find_candidate_by_email(
    email: str,
    session: AsyncSession,
) -> CandidateProfile | None:
    """Find an existing candidate profile by email address.

    Args:
        email: Email address to search for
        session: Database session

    Returns:
        CandidateProfile if found, None otherwise
    """
    result = await session.execute(
        select(CandidateProfile).where(  # pyright: ignore[reportArgumentType]
            CandidateProfile.email == email
        )
    )
    return result.scalar_one_or_none()


async def update_candidate_profile(
    candidate: CandidateProfile,
    candidate_data: CandidateProfileCreate,
    resume_path: str | None = None,
    session: AsyncSession | None = None,
) -> CandidateProfile:
    """Update an existing candidate profile with new information.

    Update strategy:
    - Always update: full_name (may have changed)
    - Update if None: phone, linkedin_url, resume_path, interview fields
    - Never overwrite: email, created_at

    Args:
        candidate: Existing CandidateProfile to update
        candidate_data: New candidate data from form
        resume_path: Optional new resume path
        session: Database session (required)

    Returns:
        Updated CandidateProfile
    """
    if session is None:
        raise ValueError("Database session is required")

    # Always update full_name (person may have changed name)
    candidate.full_name = candidate_data.full_name

    # Update if None: phone, linkedin_url, and all interview fields
    if candidate.phone is None and candidate_data.phone is not None:
        candidate.phone = candidate_data.phone

    if candidate.linkedin_url is None and candidate_data.linkedin_url is not None:
        candidate.linkedin_url = candidate_data.linkedin_url

    # Resume handling: only update if existing resume_path is None
    if candidate.resume_path is None and resume_path is not None:
        candidate.resume_path = resume_path

    # Update interview fields if None
    if candidate.service_concept is None and candidate_data.service_concept is not None:
        candidate.service_concept = candidate_data.service_concept

    if (
        candidate.salary_expectations is None
        and candidate_data.salary_expectations is not None
    ):
        candidate.salary_expectations = candidate_data.salary_expectations

    if (
        candidate.personality_weakness is None
        and candidate_data.personality_weakness is not None
    ):
        candidate.personality_weakness = candidate_data.personality_weakness

    if (
        candidate.personality_strength is None
        and candidate_data.personality_strength is not None
    ):
        candidate.personality_strength = candidate_data.personality_strength

    return candidate


async def create_candidate_profile(
    candidate_data: CandidateProfileCreate,
    job_id: int,
    resume_file: bytes | None = None,
    resume_filename: str | None = None,
    session: AsyncSession | None = None,
) -> CandidateProfileRead:
    """Create a candidate profile and application for a job.

    This is the main service method for the public application form.
    It handles:
    - Creating the CandidateProfile record
    - Uploading resume file (if provided) via storage service
    - Creating the Application record linking candidate to job
    - Sending email notification to all admins

    Args:
        candidate_data: Candidate profile data from form
        job_id: ID of the job being applied to
        resume_file: Optional resume file content (bytes)
        resume_filename: Optional resume file name
        session: Database session (required)

    Returns:
        Created CandidateProfile as CandidateProfileRead schema

    Raises:
        ValueError: If session is not provided
        JobNotFoundError: If job with job_id does not exist
        ValueError: If file upload fails
    """
    if session is None:
        raise ValueError("Database session is required")

    # Verify job exists
    result = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    # Load company profile for email notification
    from src.models import CompanyProfile

    company_result = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.id == job.company_id
        )
    )
    company = company_result.scalar_one_or_none()
    company_name = company.name if company else "Unknown Company"

    # Handle resume file upload if provided
    resume_path: str | None = None
    if resume_file is not None and resume_filename is not None:
        try:
            # Validate file type (PDF, DOC, DOCX)
            allowed_extensions = {".pdf", ".doc", ".docx"}
            file_extension = (
                resume_filename.lower().split(".")[-1] if "." in resume_filename else ""
            )
            if f".{file_extension}" not in allowed_extensions:
                raise ValueError(
                    f"Invalid file type. Allowed types: PDF, DOC, DOCX. "
                    f"Got: {file_extension}"
                )

            # Validate file size (max 10MB)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if len(resume_file) > max_size:
                raise ValueError(
                    f"File size exceeds maximum of 10MB. Got: {len(resume_file)} bytes"
                )

            if not validate_document_magic_bytes(resume_file, file_extension):
                raise ValueError(
                    "Resume file content does not match the declared file type"
                )

            # Upload file via storage service
            storage_provider: StorageProvider = get_storage_provider()
            # Determine correct MIME type based on file extension
            if file_extension == "pdf":
                content_type = "application/pdf"
            elif file_extension == "docx":
                content_type = (
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                )
            else:  # .doc
                content_type = "application/msword"

            file_identifier = await storage_provider.upload_file(
                file_content=resume_file,
                file_name=resume_filename,
                content_type=content_type,
            )

            # Store the file identifier as resume_path
            # For local storage, this will be the file key
            # For S3, this will be the S3 object key
            resume_path = file_identifier
        except Exception as e:
            raise ValueError(f"Failed to upload resume file: {e}") from e

    # Check if candidate exists by email (shadow profile logic)
    existing_candidate = await find_candidate_by_email(
        email=candidate_data.email, session=session
    )

    if existing_candidate:
        # Update existing candidate profile with new information
        candidate = await update_candidate_profile(
            candidate=existing_candidate,
            candidate_data=candidate_data,
            resume_path=resume_path,
            session=session,
        )
        await session.flush()  # Flush to ensure candidate is updated

        # Check if Application already exists for this job+candidate
        result = await session.execute(
            select(Application).where(  # pyright: ignore[reportArgumentType]
                Application.job_id == job_id,
                Application.candidate_id == candidate.id,  # type: ignore[reportArgumentType]
            )
        )
        existing_application = result.scalar_one_or_none()

        if existing_application:
            raise ApplicationAlreadyExistsError(
                job_id=job_id,
                candidate_id=candidate.id,  # type: ignore[arg-type]
            )

        # Create new Application for existing candidate
        application = Application(
            job_id=job_id,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            status=ApplicationStatus.NEW,  # Admin as Gatekeeper: starts as NEW
        )
        session.add(application)
    else:
        # Create new CandidateProfile
        candidate = CandidateProfile(
            full_name=candidate_data.full_name,
            email=candidate_data.email,
            phone=candidate_data.phone,
            resume_path=resume_path,
            linkedin_url=candidate_data.linkedin_url,
            service_concept=candidate_data.service_concept,
            salary_expectations=candidate_data.salary_expectations,
            personality_weakness=candidate_data.personality_weakness,
            personality_strength=candidate_data.personality_strength,
        )

        session.add(candidate)
        await session.flush()  # Flush to get candidate.id

        # Create Application record (linking candidate to job)
        application = Application(
            job_id=job_id,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            status=ApplicationStatus.NEW,  # Admin as Gatekeeper: starts as NEW
        )

        session.add(application)

    await session.commit()

    # Send email notification to all admins (async task)
    admin_emails = await get_all_admin_emails(session)
    if admin_emails:
        email_subject = (
            f"New Application: {candidate.full_name} applied for {job.title}"
        )
        email_body = f"""
A new candidate application has been submitted:

Candidate: {candidate.full_name}
Email: {candidate.email}
Phone: {candidate.phone or "Not provided"}
LinkedIn: {candidate.linkedin_url or "Not provided"}

Job: {job.title} (ID: {job.id})
Company: {company_name}

Application Status: NEW (requires admin approval)

Please review the application in the admin dashboard.
"""
        await enqueue_email_task(
            to=admin_emails,
            subject=email_subject,
            body=email_body,
        )

    # Refresh candidate to ensure all fields are loaded (before commit)
    await session.refresh(candidate)

    return CandidateProfileRead.model_validate(candidate)
