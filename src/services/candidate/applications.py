"""Candidate-facing application listing and detail (Sprint 11 / #609).

The candidate-facing API deliberately never exposes raw ``Application.status``
or ``admin_notes``. WITHDRAWN applications are filtered out entirely (the
candidate can re-apply per the partial unique index added in #604, so showing
a withdrawn row would be misleading — and the spec treats withdrawn rows as
if they don't exist for this candidate). Only the derived ``editable`` flag
(true iff ``status == NEW``) leaks across the boundary.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlmodel import select

from src.core.infrastructure.pagination import (
    CursorPage,
    apply_cursor,
    build_cursor_page,
    clamp_limit,
)
from src.enums import ApplicationStatus, JobStatus
from src.models import Application, Job
from src.schemas.candidates import (
    CandidateApplicationCompany,
    CandidateApplicationDetail,
    CandidateApplicationJobDetail,
    CandidateApplicationJobSummary,
    CandidateApplicationListItem,
    CandidateApplicationMyAnswers,
    CandidateApplicationResumeMeta,
)
from src.services.exceptions import ApplicationNotFoundError


def _job_summary(job: Job) -> CandidateApplicationJobSummary:
    return CandidateApplicationJobSummary(
        id=job.id,  # type: ignore[arg-type]
        title=job.title,
        closed=job.status == JobStatus.CLOSED,
    )


def _job_detail(job: Job) -> CandidateApplicationJobDetail:
    return CandidateApplicationJobDetail(
        id=job.id,  # type: ignore[arg-type]
        title=job.title,
        description=job.description,
        closed=job.status == JobStatus.CLOSED,
    )


def _company(job: Job) -> CandidateApplicationCompany:
    return CandidateApplicationCompany(id=job.company.id, name=job.company.name)


def _list_item(app: Application) -> CandidateApplicationListItem:
    return CandidateApplicationListItem(
        id=app.id,  # type: ignore[arg-type]
        submitted_at=app.created_at,
        editable=app.status == ApplicationStatus.NEW,
        job=_job_summary(app.job),
        company=_company(app.job),
    )


async def list_my_applications(
    session: AsyncSession,
    *,
    candidate_id: int,
    cursor: str | None = None,
    limit: int | None = None,
) -> CursorPage[CandidateApplicationListItem]:
    """One page of this candidate's applications, newest first.

    WITHDRAWN rows are excluded — they are invisible to the candidate via
    this endpoint, mirroring the issue's "withdrawn behaves like deleted"
    semantics.
    """
    page_size = clamp_limit(limit)
    query = select(Application).where(
        Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
    )
    query = query.options(selectinload(Application.job).selectinload(Job.company))
    query = apply_cursor(
        query,
        sort_col=Application.created_at,
        id_col=Application.id,  # pyright: ignore[reportArgumentType]
        cursor=cursor,
        limit=page_size,
    )
    rows = list((await session.execute(query)).scalars().all())
    return build_cursor_page(
        rows,
        serializer=_list_item,
        cursor_key=lambda a: (a.created_at, a.id),  # type: ignore[arg-type,return-value]
        limit=page_size,
    )


async def get_my_application(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
) -> CandidateApplicationDetail:
    """Return one application — 404 if foreign or WITHDRAWN.

    Raises ApplicationNotFoundError on miss; the router maps it to a 404 HTTP
    response. Foreign-id and withdrawn-row cases collapse to the same 404
    so the endpoint can't be used to probe other candidates' application IDs.
    """
    query = (
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.company))
        .where(
            Application.id == application_id,  # pyright: ignore[reportArgumentType]
            Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
            Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
        )
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None:
        raise ApplicationNotFoundError("Application not found")

    resume: CandidateApplicationResumeMeta | None = None
    if app.resume_path:
        resume = CandidateApplicationResumeMeta(
            filename=app.resume_filename or app.resume_path.rsplit("/", 1)[-1],
            snapshot_present=True,
        )

    return CandidateApplicationDetail(
        id=app.id,  # type: ignore[arg-type]
        submitted_at=app.created_at,
        editable=app.status == ApplicationStatus.NEW,
        job=_job_detail(app.job),
        company=_company(app.job),
        my_answers=CandidateApplicationMyAnswers(
            service_concept=app.service_concept,
            salary_expectations=app.salary_expectations,
            strength=app.strength,
            growth_area=app.growth_area,
        ),
        resume=resume,
    )


async def get_application_resume_key(
    session: AsyncSession,
    *,
    candidate_id: int,
    application_id: int,
) -> str:
    """Return the snapshotted resume's storage key for streaming.

    Raises ApplicationNotFoundError if the application is foreign, withdrawn, or
    has no resume snapshot — all three cases share a single 404 so callers
    can't probe ownership or existence separately.
    """
    query = select(Application).where(
        Application.id == application_id,  # pyright: ignore[reportArgumentType]
        Application.candidate_id == candidate_id,  # pyright: ignore[reportArgumentType]
        Application.status != ApplicationStatus.WITHDRAWN,  # pyright: ignore[reportArgumentType]
    )
    app = (await session.execute(query)).scalar_one_or_none()
    if app is None or not app.resume_path:
        raise ApplicationNotFoundError("Resume not found")
    return app.resume_path
