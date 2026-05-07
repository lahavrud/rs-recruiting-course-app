"""Unit tests for the admin jobs CRUD service layer."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ApplicationStatus, JobStatus
from src.models import Application, CandidateProfile, CompanyProfile, Job
from src.schemas import JobAdminCreate, JobUpdate
from src.services.exceptions import CompanyNotFoundError, JobNotFoundError
from src.services.jobs_admin_crud import (
    admin_create_job,
    delete_job,
    get_job,
    list_jobs,
    update_job,
)


def _payload(company_id: int, title: str = "Backend Engineer") -> JobAdminCreate:
    return JobAdminCreate(
        company_id=company_id,
        title=title,
        description="ניהול שרתים ופיתוח backend",
        requirements="3+ שנות ניסיון",
        location="תל אביב",
        salary_min=15000,
        salary_max=22000,
    )


# ── admin_create_job ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_create_job_published_by_default(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    assert job.id is not None
    assert job.status == JobStatus.PUBLISHED
    assert job.company_id == company_with_user.id


@pytest.mark.asyncio
async def test_admin_create_job_unknown_company(session: AsyncSession):
    with pytest.raises(CompanyNotFoundError):
        await admin_create_job(_payload(company_id=99999), session)


# ── get_job ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_job_returns_any_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    closed = Job(
        company_id=company_with_user.id,
        title="Closed Role",
        description="x",
        requirements="x",
        location="x",
        status=JobStatus.CLOSED,
    )
    session.add(closed)
    await session.commit()
    await session.refresh(closed)

    fetched = await get_job(closed.id, session)
    assert fetched.id == closed.id
    assert fetched.status == JobStatus.CLOSED


@pytest.mark.asyncio
async def test_get_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError):
        await get_job(99999, session)


# ── update_job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_job_partial_keeps_unset_fields(
    session: AsyncSession, company_with_user: CompanyProfile
):
    created = await admin_create_job(_payload(company_with_user.id), session)
    await session.commit()

    updated = await update_job(
        created.id,
        JobUpdate(title="Senior Backend Engineer", status=JobStatus.CLOSED),
        session,
    )
    await session.commit()

    assert updated.title == "Senior Backend Engineer"
    assert updated.status == JobStatus.CLOSED
    assert updated.description == created.description  # untouched
    assert updated.location == created.location  # untouched


@pytest.mark.asyncio
async def test_update_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError):
        await update_job(99999, JobUpdate(title="anything"), session)


# ── delete_job ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_job_cascades_applications_keeps_candidate(
    session: AsyncSession, company_with_user: CompanyProfile
):
    job_id = (await admin_create_job(_payload(company_with_user.id), session)).id
    candidate = CandidateProfile(
        full_name="Tester", email="cand@test.com", phone="050-1111111"
    )
    session.add(candidate)
    await session.flush()
    session.add(
        Application(
            job_id=job_id,
            candidate_id=candidate.id,
            status=ApplicationStatus.NEW,
        )
    )
    await session.commit()

    await delete_job(job_id, session)
    await session.commit()

    job_row = await session.execute(
        select(Job).where(Job.id == job_id)  # pyright: ignore[reportArgumentType]
    )
    assert job_row.scalar_one_or_none() is None

    app_row = await session.execute(
        select(Application).where(Application.job_id == job_id)  # pyright: ignore[reportArgumentType]
    )
    assert app_row.scalar_one_or_none() is None

    candidate_row = await session.execute(
        select(CandidateProfile).where(CandidateProfile.id == candidate.id)  # pyright: ignore[reportArgumentType]
    )
    assert candidate_row.scalar_one() is not None  # candidate survives


@pytest.mark.asyncio
async def test_delete_job_not_found(session: AsyncSession):
    with pytest.raises(JobNotFoundError):
        await delete_job(99999, session)


# ── list_jobs ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_jobs_filters_by_status(
    session: AsyncSession, company_with_user: CompanyProfile
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i, status in enumerate(
        [JobStatus.PUBLISHED, JobStatus.PUBLISHED, JobStatus.CLOSED]
    ):
        session.add(
            Job(
                company_id=company_with_user.id,
                title=f"Role {i}",
                description="x",
                requirements="x",
                location="x",
                status=status,
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.commit()

    page = await list_jobs(session, status=JobStatus.PUBLISHED)
    assert {item.title for item in page.items} == {"Role 0", "Role 1"}
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_jobs_paginates_through_all(
    session: AsyncSession, company_with_user: CompanyProfile
):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(15):
        session.add(
            Job(
                company_id=company_with_user.id,
                title=f"Role {i:02d}",
                description="x",
                requirements="x",
                location="x",
                status=JobStatus.PUBLISHED,
                created_at=base + timedelta(minutes=i),
            )
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    while True:
        page = await list_jobs(session, cursor=cursor, limit=5)
        seen.extend(item.title for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(seen) == 15
    assert len(set(seen)) == 15
    # newest-first: last-created (Role 14) appears first
    assert seen[0] == "Role 14"
    assert seen[-1] == "Role 00"
