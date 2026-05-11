"""Admin service layer for direct CompanyProfile CRUD.

These functions are addressed by `CompanyProfile.id`, so they work uniformly
for both with-user and admin-created (`user_id=None`) profiles. The
approval/rejection lifecycle that's keyed by `User.id` lives in
`admin_companies.py`.
"""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.database_helpers import get_by_id_or_raise
from src.models import Application, CompanyProfile, Job
from src.schemas import (
    CompanyProfileAdminCreate,
    CompanyProfileAdminUpdate,
    CompanyProfileRead,
)
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError


async def get_company_profile(
    profile_id: int, session: AsyncSession
) -> CompanyProfileRead:
    """Fetch a single CompanyProfile by its primary key.

    Raises:
        CompanyNotFoundError: If no company profile with that id exists.
    """
    profile = await get_by_id_or_raise(
        session,
        CompanyProfile,
        profile_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )
    return CompanyProfileRead.model_validate(profile)


async def admin_create_company(
    data: CompanyProfileAdminCreate, session: AsyncSession
) -> CompanyProfileRead:
    """Create a CompanyProfile directly, without a user account.

    Used when an admin wants to post jobs against a company that has not
    been onboarded yet. `user_id` is left null; the company can be linked
    to a real user later by extending this flow.
    """
    profile = CompanyProfile(
        user_id=None,
        name=data.name,
        company_id=data.company_id,
        address=data.address,
        contact_first_name=data.contact_first_name,
        contact_last_name=data.contact_last_name,
        contact_mobile_phone=data.contact_mobile_phone,
        contact_landline_phone=data.contact_landline_phone,
    )
    session.add(profile)
    await session.flush()
    await session.refresh(profile)
    return CompanyProfileRead.model_validate(profile)


async def delete_orphan_company_profile(profile_id: int, session: AsyncSession) -> None:
    """Delete an admin-created CompanyProfile that has no user account.

    Only deletes profiles with user_id=None (orphan profiles). Raises
    CompanyNotPendingError if the profile is linked to a user, to prevent
    accidental deletion of active or pending company accounts.

    Delete order: Applications → Jobs → CompanyProfile.

    Raises:
        CompanyNotFoundError: If no profile with that id exists.
        CompanyNotPendingError: If the profile is linked to a user account.
    """
    profile = await get_by_id_or_raise(
        session,
        CompanyProfile,
        profile_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )
    if profile.user_id is not None:
        raise CompanyNotPendingError(
            f"Company profile {profile_id} is linked to user {profile.user_id}; "
            "use the company-user delete endpoint instead"
        )

    job_ids_result = await session.execute(
        select(Job.id).where(Job.company_id == profile_id)  # pyright: ignore[reportArgumentType]
    )
    job_ids = [r[0] for r in job_ids_result.all()]
    if job_ids:
        await session.execute(
            delete(Application).where(Application.job_id.in_(job_ids))  # pyright: ignore[reportAttributeAccessIssue]
        )
        await session.execute(
            delete(Job).where(Job.id.in_(job_ids))  # pyright: ignore[reportAttributeAccessIssue]
        )
        await session.flush()

    await session.delete(profile)
    await session.flush()


async def update_company_profile(
    profile_id: int,
    data: CompanyProfileAdminUpdate,
    session: AsyncSession,
) -> CompanyProfileRead:
    """Apply a partial update to a CompanyProfile.

    Only fields explicitly set on the input schema are updated; unset fields
    leave the existing value untouched.

    Raises:
        CompanyNotFoundError: If no company profile with that id exists.
    """
    profile = await get_by_id_or_raise(
        session,
        CompanyProfile,
        profile_id,
        lambda pk: CompanyNotFoundError(f"Company profile {pk} not found"),
    )

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)

    await session.flush()
    await session.refresh(profile)
    return CompanyProfileRead.model_validate(profile)
