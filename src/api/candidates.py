"""Candidate endpoints for public application form."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.transactions import transactional
from src.schemas import CandidateProfileCreate, CandidateProfileRead
from src.services.applications import create_candidate_profile
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
    growth_area: str | None,
    strength: str | None,
    privacy_accepted: bool,
    terms_accepted: bool,
    resume: UploadFile | None,
    request: Request,
    session: AsyncSession,
) -> CandidateProfileRead:
    if not privacy_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="privacy_consent_required",
        )
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="terms_consent_required",
        )

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
    )

    try:
        async with transactional(session):
            candidate = await create_candidate_profile(
                candidate_data=candidate_data,
                job_id=job_id,
                resume_file=resume_file,
                resume_filename=resume_filename,
                session=session,
                consent_ip=client_ip(request),
                consent_ua=request.headers.get("user-agent"),
                service_concept=service_concept,
                salary_expectations=salary_expectations,
                strength=strength,
                growth_area=growth_area,
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
    request: Request,
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None),
    salary_expectations: str | None = Form(None),
    growth_area: str | None = Form(None),
    strength: str | None = Form(None),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
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
        growth_area=growth_area,
        strength=strength,
        privacy_accepted=privacy_accepted,
        terms_accepted=terms_accepted,
        resume=resume,
        request=request,
        session=session,
    )


@jobs_apply_router.post(
    "/{job_id}/apply",
    response_model=CandidateProfileRead,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_job_by_path(
    job_id: int,
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    linkedin_url: str | None = Form(None),
    service_concept: str | None = Form(None),
    salary_expectations: str | None = Form(None),
    growth_area: str | None = Form(None),
    strength: str | None = Form(None),
    privacy_accepted: bool = Form(...),
    terms_accepted: bool = Form(...),
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
        growth_area=growth_area,
        strength=strength,
        privacy_accepted=privacy_accepted,
        terms_accepted=terms_accepted,
        resume=resume,
        request=request,
        session=session,
    )
