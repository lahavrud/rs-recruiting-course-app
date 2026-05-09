"""Candidate endpoints for public application form."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.candidates import create_candidate_profile
from src.services.exceptions import ApplicationAlreadyExistsError, JobNotFoundError

router = APIRouter(prefix="/api/candidates", tags=["candidates"])
jobs_apply_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _apply_common(
    job_id: int,
    full_name: str,
    email: str,
    phone: str,
    linkedin_url: str | None,
    service_concept: str | None,
    salary_expectations: str | None,
    personality_weakness: str | None,
    personality_strength: str | None,
    resume: UploadFile | None,
    session: AsyncSession,
) -> CandidateProfileRead:
    resume_file: bytes | None = None
    resume_filename: str | None = None
    if resume is not None:
        resume_file = await resume.read()
        resume_filename = resume.filename

    candidate_data = CandidateProfileCreate(
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        personality_weakness=personality_weakness,
        personality_strength=personality_strength,
    )

    try:
        async with transactional(session):
            candidate = await create_candidate_profile(
                candidate_data=candidate_data,
                job_id=job_id,
                resume_file=resume_file,
                resume_filename=resume_filename,
                session=session,
            )
        return candidate
    except (JobNotFoundError, ApplicationAlreadyExistsError) as e:
        raise service_exception_to_http(e) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "/apply",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job(
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None),
    salary_expectations: str | None = Form(None),
    personality_weakness: str | None = Form(None),
    personality_strength: str | None = Form(None),
    resume: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    return await _apply_common(
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        personality_weakness=personality_weakness,
        personality_strength=personality_strength,
        resume=resume,
        session=session,
    )


@jobs_apply_router.post(
    "/{job_id}/apply",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job_by_path(
    job_id: int,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None),
    salary_expectations: str | None = Form(None),
    personality_weakness: str | None = Form(None),
    personality_strength: str | None = Form(None),
    resume: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> CandidateProfileRead:
    return await _apply_common(
        job_id=job_id,
        full_name=full_name,
        email=email,
        phone=phone,
        linkedin_url=linkedin_url,
        service_concept=service_concept,
        salary_expectations=salary_expectations,
        personality_weakness=personality_weakness,
        personality_strength=personality_strength,
        resume=resume,
        session=session,
    )
