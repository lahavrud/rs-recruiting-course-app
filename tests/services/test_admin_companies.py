"""Unit tests for admin_companies service layer."""

import base64
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.security import get_password_hash
from src.enums import UserRole
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.admin_companies import (
    approve_company,
    delete_active_company,
    get_all_admin_emails,
    list_active_companies,
    list_pending_companies,
    reject_company,
)
from src.services.auth import register_company_user
from src.services.exceptions import CompanyNotFoundError, CompanyNotPendingError

_SIG = base64.b64encode(b"fake-sig").decode()
_LOGO = b"fake-logo"


def _company_create(email: str, name: str) -> UserCreate:
    return UserCreate(
        email=email,
        password="SecurePass1!",
        company_profile=CompanyProfileCreate(
            name=name,
            company_id="123456789",
            contact_first_name="ישראל",
            contact_last_name="ישראלי",
            contact_mobile_phone="0501234567",
        ),
    )


async def _register(data: UserCreate, session: AsyncSession) -> User:
    result = await register_company_user(
        data, session, _LOGO, "logo.png", "image/png", _SIG
    )
    await session.commit()
    return result.user


# ── get_all_admin_emails ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_all_admin_emails(session: AsyncSession):
    admin1 = User(
        email="admin1@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    admin2 = User(
        email="admin2@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    inactive_admin = User(
        email="admin3@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    company = User(
        email="company@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add_all([admin1, admin2, inactive_admin, company])
    await session.commit()

    emails = await get_all_admin_emails(session)
    assert set(emails) == {"admin1@example.com", "admin2@example.com"}


# ── list_pending_companies ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pending_companies_empty(session: AsyncSession):
    assert await list_pending_companies(session) == []


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_list_pending_companies(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    await _register(_company_create("p1@example.com", "Company 1"), session)
    await _register(_company_create("p2@example.com", "Company 2"), session)

    # Active company should not appear
    user = await _register(_company_create("active@example.com", "Active Co"), session)
    res = await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    res.scalar_one().is_active = True
    await session.commit()

    companies = await list_pending_companies(session)
    assert len(companies) == 2
    emails = {c["user"].email for c in companies}
    assert emails == {"p1@example.com", "p2@example.com"}
    assert all(not c["user"].is_active for c in companies)


# ── approve_company ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.admin_companies.enqueue_email_task")
async def test_approve_company_success(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("approve@example.com", "Approve Co"), session
    )
    assert not user.is_active

    result = await approve_company(user.id, session)
    await session.commit()

    assert result["user"].is_active is True
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    assert db_user.is_active is True


@pytest.mark.asyncio
async def test_approve_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await approve_company(99999, session)


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_approve_company_already_approved(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("already@example.com", "Already Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await approve_company(user.id, session)


@pytest.mark.asyncio
async def test_approve_company_wrong_role(session: AsyncSession):
    admin = User(
        email="wrongrole@example.com",
        hashed_password=get_password_hash("password"),
        role=UserRole.ADMIN,
        is_active=False,
    )
    session.add(admin)
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await approve_company(admin.id, session)


# ── reject_company ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.admin_companies.enqueue_email_task")
async def test_reject_company_success(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(_company_create("reject@example.com", "Reject Co"), session)
    user_id = user.id

    cp_res = await session.execute(
        select(CompanyProfile).where(CompanyProfile.user_id == user_id)  # pyright: ignore[reportArgumentType]
    )
    cp_id = cp_res.scalar_one().id

    await reject_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(CompanyProfile).where(CompanyProfile.id == cp_id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_reject_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await reject_company(99999, session)


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_reject_company_already_approved(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("rejectactive@example.com", "Active Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()

    with pytest.raises(CompanyNotPendingError):
        await reject_company(user.id, session)


# ── list_active_companies ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_list_active_companies_empty(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    # Pending company should not appear
    await _register(_company_create("pending@example.com", "Pending Co"), session)
    assert await list_active_companies(session) == []


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_list_active_companies(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    for email, name in [("a@example.com", "A Co"), ("b@example.com", "B Co")]:
        user = await _register(_company_create(email, name), session)
        db_user = (
            await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
        ).scalar_one()
        db_user.is_active = True
    await session.commit()

    companies = await list_active_companies(session)
    assert len(companies) == 2
    emails = {c.user.email for c in companies}
    assert emails == {"a@example.com", "b@example.com"}
    assert all(c.user.is_active for c in companies)


# ── delete_active_company ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_delete_active_company_no_jobs(mock_email, session: AsyncSession):
    mock_email.return_value = "job-id"
    user = await _register(_company_create("del@example.com", "Del Co"), session)
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.commit()
    user_id = user.id

    await delete_active_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
@patch("src.services.auth.enqueue_email_task")
async def test_delete_active_company_cascades_jobs_and_applications(
    mock_email, session: AsyncSession
):
    mock_email.return_value = "job-id"
    user = await _register(
        _company_create("cascade@example.com", "Cascade Co"), session
    )
    db_user = (
        await session.execute(select(User).where(User.id == user.id))  # pyright: ignore[reportArgumentType]
    ).scalar_one()
    db_user.is_active = True
    await session.flush()

    cp = (
        await session.execute(
            select(CompanyProfile).where(CompanyProfile.user_id == user.id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one()

    job = Job(
        title="Engineer",
        description="Desc",
        requirements="Python",
        location="TLV",
        company_id=cp.id,
    )
    session.add(job)
    await session.flush()

    candidate = CandidateProfile(full_name="Test Candidate", email="cand@example.com")
    session.add(candidate)
    await session.flush()

    app = Application(job_id=job.id, candidate_id=candidate.id)
    session.add(app)
    await session.commit()

    job_id = job.id
    app_id = app.id
    user_id = user.id

    await delete_active_company(user_id, session)
    await session.commit()

    assert (
        await session.execute(select(User).where(User.id == user_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(select(Job).where(Job.id == job_id))  # pyright: ignore[reportArgumentType]
    ).scalar_one_or_none() is None
    assert (
        await session.execute(
            select(Application).where(Application.id == app_id)  # pyright: ignore[reportArgumentType]
        )
    ).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_active_company_not_found(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await delete_active_company(99999, session)
