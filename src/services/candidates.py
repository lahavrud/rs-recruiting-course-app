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
    - Update if None: linkedin_url, resume_path, interview fields
    - Never overwrite: email, phone, created_at
    """
    if session is None:
        raise ValueError("Database session is required")

    candidate.full_name = candidate_data.full_name

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
