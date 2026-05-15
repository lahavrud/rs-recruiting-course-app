"""Candidate profile primitives: lookup + partial update.

The heavy apply-flow (file validation, storage upload, dup detection,
email side effects) lives in `src/services/applications.py`. This
module only owns the small pieces that operate on a single
`CandidateProfile` row.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CandidateProfile
from src.schemas import CandidateProfileCreate


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
    - Update if None: linkedin_url, resume_path
    - Never overwrite: email, phone, created_at
    """
    if session is None:
        raise ValueError("Database session is required")

    candidate.full_name = candidate_data.full_name

    if candidate.linkedin_url is None and candidate_data.linkedin_url is not None:
        candidate.linkedin_url = candidate_data.linkedin_url
    if candidate.resume_path is None and resume_path is not None:
        candidate.resume_path = resume_path

    return candidate
