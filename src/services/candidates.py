"""Candidate service layer for public application form."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.transactions import defer_after_commit
from src.core.services.file_validation import validate_document_magic_bytes
from src.core.services.storage import StorageProvider, get_storage_provider
from src.core.tasks import enqueue_email_task
from src.enums import ApplicationStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.admin_companies import get_all_admin_emails
from src.services.exceptions import ApplicationAlreadyExistsError, JobNotFoundError
from src.templates.email import (
    build_application_received_html,
    build_new_application_admin_html,
)

_ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
_MAX_RESUME_BYTES = 10 * 1024 * 1024  # 10 MB
_MIME_BY_EXT = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
}


async def find_candidate_by_email(
    email: str,
    session: AsyncSession,
) -> CandidateProfile | None:
    """Find an existing candidate profile by email address."""
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
    """
    if session is None:
        raise ValueError("Database session is required")

    candidate.full_name = candidate_data.full_name

    if candidate.phone is None and candidate_data.phone is not None:
        candidate.phone = candidate_data.phone
    if candidate.linkedin_url is None and candidate_data.linkedin_url is not None:
        candidate.linkedin_url = candidate_data.linkedin_url
    if candidate.resume_path is None and resume_path is not None:
        candidate.resume_path = resume_path
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


# ── Private helpers ───────────────────────────────────────────────────────────


async def _validate_and_upload_resume(
    resume_file: bytes,
    resume_filename: str,
    storage: StorageProvider,
) -> str:
    """Validate resume file (type, size, magic bytes) and upload it.

    Returns the storage file key. Raises ValueError on any validation failure.
    """
    ext = resume_filename.lower().rsplit(".", 1)[-1] if "." in resume_filename else ""
    if f".{ext}" not in _ALLOWED_EXTENSIONS:
        raise ValueError(f"Invalid file type. Allowed: PDF, DOC, DOCX. Got: {ext}")
    if len(resume_file) > _MAX_RESUME_BYTES:
        raise ValueError(
            f"File size exceeds maximum of 10MB. Got: {len(resume_file)} bytes"
        )
    if not validate_document_magic_bytes(resume_file, ext):
        raise ValueError("Resume file content does not match the declared file type")

    content_type = _MIME_BY_EXT.get(ext, "application/octet-stream")
    return await storage.upload_file(
        file_content=resume_file,
        file_name=f"resumes/{resume_filename}",
        content_type=content_type,
    )


async def _upsert_candidate_and_application(
    session: AsyncSession,
    candidate_data: CandidateProfileCreate,
    job_id: int,
    resume_path: str | None,
) -> CandidateProfile:
    """Find-or-create the candidate profile and create the application row.

    Raises ApplicationAlreadyExistsError if the candidate already applied.
    Returns the CandidateProfile (not yet committed).
    """
    existing = await find_candidate_by_email(
        email=candidate_data.email, session=session
    )

    if existing:
        candidate = await update_candidate_profile(
            candidate=existing,
            candidate_data=candidate_data,
            resume_path=resume_path,
            session=session,
        )
        await session.flush()

        dup = await session.execute(
            select(Application).where(  # pyright: ignore[reportArgumentType]
                Application.job_id == job_id,
                Application.candidate_id == candidate.id,  # type: ignore[reportArgumentType]
            )
        )
        if dup.scalar_one_or_none():
            raise ApplicationAlreadyExistsError(
                job_id=job_id,
                candidate_id=candidate.id,  # type: ignore[arg-type]
            )
    else:
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
        await session.flush()

    session.add(
        Application(
            job_id=job_id,
            candidate_id=candidate.id,  # type: ignore[arg-type]
            status=ApplicationStatus.NEW,
        )
    )
    return candidate


async def _send_application_emails(
    candidate: CandidateProfile,
    job: Job,
    company_name: str,
    session: AsyncSession,
) -> None:
    """Enqueue confirmation email to the candidate and notification to admins."""
    await enqueue_email_task(
        to=candidate.email,
        subject=f"מועמדותך למשרת '{job.title}' התקבלה",
        body=(
            f"שלום {candidate.full_name},\n\n"
            f"קיבלנו את מועמדותך למשרת '{job.title}'. צוות RS Recruiting "
            "יבחן את הפרטים בקרוב ויחזור אליך עם עדכון."
        ),
        html_body=build_application_received_html(
            candidate_name=candidate.full_name,
            job_title=job.title,
        ),
    )

    if settings.admin_notification_email:
        admin_recipients: list[str] | str = settings.admin_notification_email
    else:
        admin_recipients = await get_all_admin_emails(session)

    if admin_recipients:
        admin_url = f"{settings.frontend_base_url}/admin/applications"
        await enqueue_email_task(
            to=admin_recipients,
            subject=f"מועמדות חדשה למשרת '{job.title}' — {candidate.full_name}",
            body=(
                f"מועמדות חדשה התקבלה:\n\n"
                f"שם: {candidate.full_name}\n"
                f'דוא"ל: {candidate.email}\n'
                f"טלפון: {candidate.phone or 'לא צויין'}\n"
                f"משרה: {job.title}\n"
                f"חברה: {company_name}\n\n"
                f"מעבר לניהול: {admin_url}"
            ),
            html_body=build_new_application_admin_html(
                candidate_name=candidate.full_name,
                candidate_email=candidate.email,
                candidate_phone=candidate.phone,
                candidate_linkedin=candidate.linkedin_url,
                job_title=job.title,
                company_name=company_name,
                admin_url=admin_url,
            ),
        )


# ── Public entry point ────────────────────────────────────────────────────────


async def create_candidate_profile(
    candidate_data: CandidateProfileCreate,
    job_id: int,
    resume_file: bytes | None = None,
    resume_filename: str | None = None,
    session: AsyncSession | None = None,
) -> CandidateProfileRead:
    """Create a candidate profile and application for a job.

    Raises:
        ValueError: If session is missing or file upload fails.
        JobNotFoundError: If the job does not exist.
        ApplicationAlreadyExistsError: If the candidate already applied.
    """
    if session is None:
        raise ValueError("Database session is required")

    job_row = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    job = job_row.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job with ID {job_id} not found")

    company_row = await session.execute(
        select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
            CompanyProfile.id == job.company_id
        )
    )
    company = company_row.scalar_one_or_none()
    company_name = company.name if company else "Unknown Company"

    resume_path: str | None = None
    if resume_file is not None and resume_filename is not None:
        try:
            resume_path = await _validate_and_upload_resume(
                resume_file, resume_filename, get_storage_provider()
            )
        except Exception as e:
            raise ValueError(f"Failed to upload resume file: {e}") from e

    candidate = await _upsert_candidate_and_application(
        session, candidate_data, job_id, resume_path
    )
    await session.flush()
    await session.refresh(candidate)

    _candidate_snapshot = candidate
    _job_snapshot = job
    _company_name_snapshot = company_name
    defer_after_commit(
        lambda: _send_application_emails(
            _candidate_snapshot, _job_snapshot, _company_name_snapshot, session
        )
    )
    return CandidateProfileRead.model_validate(candidate)
