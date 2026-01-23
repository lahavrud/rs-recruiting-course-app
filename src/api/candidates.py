"""Candidate endpoints for public application form."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.candidates import create_candidate_profile
from src.services.exceptions import JobNotFoundError

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.post(
    "/apply",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job(
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None),
    salary_expectations: str | None = Form(None),
    military_service_details: str | None = Form(None),
    transportation: str | None = Form(None),
    personality_weakness: str | None = Form(None),
    personality_strength: str | None = Form(None),
    resume: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    """Submit a candidate application for a job.

    This is a public endpoint (no authentication required).
    Accepts multipart form data including optional resume file upload.

    Args:
        job_id: ID of the job being applied to
        full_name: Candidate's full name
        email: Candidate's email address
        phone: Candidate's phone number (optional)
        linkedin_url: Candidate's LinkedIn profile URL (optional)
        service_concept: Service concept response (optional)
        salary_expectations: Salary expectations (optional)
        military_service_details: Military service details (optional)
        transportation: Transportation information (optional)
        personality_weakness: Personality weakness (optional)
        personality_strength: Personality strength (optional)
        resume: Optional resume file (PDF, DOC, or DOCX, max 10MB)
        session: Database session

    Returns:
        Created CandidateProfile as CandidateProfileRead schema

    Raises:
        HTTPException: If job not found, validation fails, or file upload fails
    """
    # Read resume file if provided
    resume_file: bytes | None = None
    resume_filename: str | None = None
    if resume is not None:
        resume_file = await resume.read()
        resume_filename = resume.filename

    # Create CandidateProfileCreate schema from form data
    candidate_data = CandidateProfileCreate(
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        military_service_details=military_service_details,
        transportation=transportation,
        personality_weakness=personality_weakness,
        personality_strength=personality_strength,
    )

    try:
        candidate = await create_candidate_profile(
            candidate_data=candidate_data,
            job_id=job_id,
            resume_file=resume_file,
            resume_filename=resume_filename,
            session=session,
        )
        return candidate
    except JobNotFoundError as e:
        raise service_exception_to_http(e) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
