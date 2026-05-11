# ruff: noqa: E402  -- env var must be set before src imports (see _TEST_JWT_SECRET below)
"""Shared pytest fixtures for all tests."""

import base64 as _base64
import os
import struct as _struct
import zlib as _zlib
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Single source of truth for the test JWT secret.
# Set with os.environ[] (not setdefault) so it always wins over any value that
# might already be in the environment, and so every xdist worker process gets
# the same predictable value at import time — before settings is loaded.
_TEST_JWT_SECRET = "test-secret-key-min-32-chars-for-testing!"
os.environ["JWT_SECRET_KEY"] = _TEST_JWT_SECRET

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import (
    get_current_admin,
    get_current_company,
    get_current_user,
)
from src.core.infrastructure.security import get_password_hash
from src.core.infrastructure.transactions import transactional
from src.enums import ApplicationStatus, JobStatus, UserRole
from src.main import app
from src.models import Application, CandidateProfile, CompanyProfile, Job, User
from src.schemas import CompanyProfileCreate, UserCreate
from src.services.auth import register_company_user

_EMAIL_TASK_TARGETS = [
    "src.services.auth.enqueue_email_task",
    "src.services.admin_companies.enqueue_email_task",
    "src.services.jobs.enqueue_email_task",
    "src.services.jobs_admin.enqueue_email_task",
    "src.services.applications.enqueue_email_task",
    "src.services.password_reset.enqueue_email_task",
    # applications_admin no longer imports enqueue_email_task directly;
    # the router enqueues after commit — patch at the router level instead.
    "src.api.admin_applications.enqueue_email_task",
]


@pytest.fixture(autouse=True)
def mock_enqueue_email():
    """Patch enqueue_email_task in every service module for all tests.

    Prevents any test from trying to connect to Redis. Each service imports
    enqueue_email_task with 'from src.core.tasks import ...', creating a local
    binding, so each module must be patched individually.
    """
    patches = [patch(target, new_callable=AsyncMock) for target in _EMAIL_TASK_TARGETS]
    for p in patches:
        p.start()
    yield
    for p in patches:
        p.stop()


@pytest.fixture(autouse=True)
def _provide_post_commit_hooks_context():
    """Establish an empty post-commit hooks contextvar for every test.

    Tests that bypass routes and call services directly never enter
    transactional() — without this, defer_after_commit() would raise
    RuntimeError. Tests that need the deferred hooks to actually execute
    (so that @patch mocks observe the calls) should still wrap their service
    call in transactional() inside the test body, where mocks are active.
    Tests that don't care whether the hook runs are unaffected.
    """
    from src.core.infrastructure.transactions import _post_commit_hooks

    token = _post_commit_hooks.set([])
    try:
        yield
    finally:
        _post_commit_hooks.reset(token)


@pytest.fixture(autouse=True)
def mock_password_reset_rate_limit():
    """Disable the per-email password-reset rate limit in tests.

    The real implementation increments a Redis counter — across multiple test
    runs against a shared local Redis, a victim email accumulates count and
    the limit starts rejecting tokens, surfacing as flaky test failures.
    """
    with patch(
        "src.services.password_reset._per_email_rate_limit_ok",
        new_callable=AsyncMock,
        return_value=True,
    ):
        yield


@pytest.fixture(autouse=True)
def mock_auth_redis():
    """Patch Redis-backed auth helpers for all tests (no Redis in CI).

    Mocks:
    - lockout check / record / clear (no-ops — any login succeeds)
    - access token blacklist check (always returns False — no token is revoked)
    """
    with (
        patch("src.services.auth._check_lockout", new_callable=AsyncMock),
        patch("src.services.auth._record_failed_attempt", new_callable=AsyncMock),
        patch("src.services.auth._clear_failed_attempts", new_callable=AsyncMock),
        patch(
            "src.core.infrastructure.security.is_access_token_blacklisted",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_invite_tokens():
    """Patch invite token functions for all tests to prevent Redis connections.

    validate_invite_token is a no-op (any token is valid) and consume_invite_token
    is a no-op. Tests that want to test rejection pass the mock in via the fixture.
    """
    with (
        patch(
            "src.api.auth.validate_invite_token", new_callable=AsyncMock
        ) as mock_validate,
        patch("src.api.auth.consume_invite_token", new_callable=AsyncMock),
        patch("src.api.invites.validate_invite_token", new_callable=AsyncMock),
        patch(
            "src.services.admin_invites.generate_invite_token",
            new_callable=AsyncMock,
            return_value=(
                "test-invite-token-abc123",
                datetime(2099, 1, 1, tzinfo=timezone.utc),
            ),
        ),
    ):
        yield mock_validate


@pytest.fixture(autouse=True)
def mock_storage_provider():
    """Patch storage provider for all tests — prevents real S3/disk uploads."""
    mock = MagicMock()
    mock.upload_file = AsyncMock(return_value="logos/test-logo.png")
    with patch("src.services.auth.get_storage_provider", return_value=mock):
        yield mock


_BASE_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/rs_recruitment",
)

# Each xdist worker gets its own database so they don't fight over the shared
# table.delete() cleanup. Solo (non-xdist) runs keep the original DB name.
WORKER_ID = os.environ.get("PYTEST_XDIST_WORKER", "master")


def _per_worker_url(base_url: str, worker_id: str) -> str:
    if worker_id == "master":
        return base_url
    base, sep, dbname = base_url.rpartition("/")
    db_only, qs_sep, qs = dbname.partition("?")
    return f"{base}{sep}{db_only}_{worker_id}{qs_sep}{qs}"


def _admin_url(base_url: str) -> str:
    """URL for the postgres maintenance DB — used to CREATE/DROP per-worker DBs."""
    base, sep, dbname = base_url.rpartition("/")
    _db_only, qs_sep, qs = dbname.partition("?")
    return f"{base}{sep}postgres{qs_sep}{qs}"


def _per_worker_dbname(base_url: str, worker_id: str) -> str:
    _, _, dbname = base_url.rpartition("/")
    db_only, _, _ = dbname.partition("?")
    return f"{db_only}_{worker_id}"


TEST_DATABASE_URL = _per_worker_url(_BASE_DATABASE_URL, WORKER_ID)

# Several test modules read DATABASE_URL directly at import time to build their
# own engines (tests/api/test_auth.py, tests/core/infrastructure/test_dependencies.py,
# etc.). Rewrite the env var here so those reads pick up the per-worker URL too.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

test_engine = create_async_engine(
    TEST_DATABASE_URL, echo=False, future=True, poolclass=NullPool
)

TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session", autouse=True)
def setup_testing_environment():
    """Set up testing environment + per-worker database before any tests run.

    Solo runs use the existing DATABASE_URL DB. Under pytest-xdist each worker
    creates its own DB (rs_recruitment_test_gw0, _gw1, …) so workers cannot
    collide on the shared autouse table.delete() cleanup.
    """
    # Enable testing mode (disables rate limiting and config validation)
    settings.testing = True

    if WORKER_ID != "master":
        import asyncio

        worker_dbname = _per_worker_dbname(_BASE_DATABASE_URL, WORKER_ID)
        admin_url = _admin_url(_BASE_DATABASE_URL)

        async def _create_db() -> None:
            engine = create_async_engine(
                admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
            )
            try:
                async with engine.connect() as conn:
                    from sqlalchemy import text

                    await conn.execute(
                        text(f'DROP DATABASE IF EXISTS "{worker_dbname}"')
                    )
                    await conn.execute(text(f'CREATE DATABASE "{worker_dbname}"'))
            finally:
                await engine.dispose()

        async def _drop_db() -> None:
            engine = create_async_engine(
                admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
            )
            try:
                async with engine.connect() as conn:
                    from sqlalchemy import text

                    await conn.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                            f" WHERE datname = '{worker_dbname}'"
                        )
                    )
                    await conn.execute(
                        text(f'DROP DATABASE IF EXISTS "{worker_dbname}"')
                    )
            finally:
                await engine.dispose()

        asyncio.run(_create_db())
        try:
            yield
        finally:
            # Engine may have lingering connections; release them before dropping.
            asyncio.run(test_engine.dispose())
            asyncio.run(_drop_db())
            settings.testing = False
        return

    yield
    settings.testing = False


@pytest.fixture(scope="function", autouse=True)
async def test_db() -> AsyncGenerator[None, None]:
    """Create test database tables and clean up between tests.

    Optimized approach:
    1. Create tables once (first test)
    2. Use DELETE statements to clean data between tests (faster than DROP/CREATE)
    3. Drop tables only at the end
    """
    # Create tables if they don't exist (idempotent)
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    # Dialect-agnostic cleanup using SQLModel metadata table references.
    # Avoids raw SQL with "user" which is a reserved word in PostgreSQL.
    # Reversed sorted_tables respects FK dependency order automatically.
    async with test_engine.begin() as conn:
        for table in reversed(SQLModel.metadata.sorted_tables):
            await conn.execute(table.delete())


@pytest.fixture
async def session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session.

    Each test gets a fresh session. Data is cleaned up via test_db fixture.
    """
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
def mock_s3_bucket():
    """Fixture providing mock S3 bucket configuration.

    Can be reused across multiple test files.
    """
    return {
        "bucket_name": "test-bucket",
        "region": "us-east-1",
    }


# ==================== User Fixtures ====================


def _make_company_profile_create(name: str) -> CompanyProfileCreate:
    return CompanyProfileCreate(
        name=name,
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )


def _make_png() -> bytes:
    """Generate a minimal valid 1×1 white PNG for use in tests."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = _zlib.crc32(tag + data) & 0xFFFFFFFF
        return _struct.pack(">I", len(data)) + tag + data + _struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", _struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", _zlib.compress(b"\x00\xff\xff\xff"))
        + _chunk(b"IEND", b"")
    )


FAKE_PNG: bytes = _make_png()
FAKE_LOGO: bytes = FAKE_PNG
FAKE_SIG_B64: str = _base64.b64encode(FAKE_PNG).decode()

_STRONG_PASSWORD = "SecurePass1!"


@pytest.fixture
async def company_user(test_db) -> User:
    """Create a pending (inactive) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="company@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Test Company"),
        )
        async with transactional(session):
            result = await register_company_user(
                user_data,
                session,
                FAKE_LOGO,
                "logo.png",
                "image/png",
                FAKE_SIG_B64,
            )
        return result.user


@pytest.fixture
async def approved_company_user(test_db) -> User:
    """Create an approved (active) company user for testing."""
    async with TestSessionLocal() as session:
        user_data = UserCreate(
            email="approved@test.com",
            password=_STRONG_PASSWORD,
            company_profile=_make_company_profile_create("Approved Company"),
        )
        async with transactional(session):
            result = await register_company_user(
                user_data,
                session,
                FAKE_LOGO,
                "logo.png",
                "image/png",
                FAKE_SIG_B64,
            )
        result.user.is_active = True
        await session.commit()
        return result.user


@pytest.fixture
async def company_profile(approved_company_user: User) -> CompanyProfile:
    """Get company profile for approved company user."""
    async with TestSessionLocal() as session:
        result = await session.execute(
            select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                CompanyProfile.user_id == approved_company_user.id
            )
        )
        return result.scalar_one()


@pytest.fixture
async def admin_user(test_db) -> User:
    """Create an admin user for testing."""
    async with TestSessionLocal() as session:
        admin = User(
            email="admin@test.com",
            hashed_password=get_password_hash("adminpassword"),
            role=UserRole.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


@pytest.fixture
async def company_with_user(session: AsyncSession) -> CompanyProfile:
    """Create a company user and profile for service layer testing."""
    user = User(
        email="company@test.com",
        hashed_password="hashed",
        role=UserRole.COMPANY,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    company = CompanyProfile(
        user_id=user.id,
        name="Test Company",
        company_id="123456789",
        address="רח׳ הדוגמה 1, תל אביב",
        contact_first_name="ישראל",
        contact_last_name="ישראלי",
        contact_mobile_phone="0501234567",
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    assert company.id is not None
    return company


# ==================== Job Fixtures ====================


@pytest.fixture
async def pending_job(company_profile: CompanyProfile) -> Job:
    """Create a pending job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
            status=JobStatus.PENDING_APPROVAL,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def published_job(company_profile: CompanyProfile) -> Job:
    """Create a published job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Senior Python Developer",
            description="We are looking for a senior Python developer...",
            requirements="5+ years experience with Python, FastAPI, PostgreSQL",
            location="Tel Aviv, Israel",
            salary_min=15000,
            salary_max=25000,
            status=JobStatus.PUBLISHED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


@pytest.fixture
async def closed_job(company_profile: CompanyProfile) -> Job:
    """Create a closed job for testing."""
    async with TestSessionLocal() as session:
        job = Job(
            company_id=company_profile.id,
            title="Closed Position",
            description="This position is closed",
            requirements="N/A",
            location="N/A",
            salary_min=10000,
            salary_max=15000,
            status=JobStatus.CLOSED,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job


# ==================== Application Fixtures ====================


@pytest.fixture
async def candidate_profile(test_db) -> CandidateProfile:
    """Create a candidate profile for testing."""
    async with TestSessionLocal() as session:
        candidate = CandidateProfile(
            full_name="Jane Candidate",
            email="jane@candidate.com",
            phone="555-1234",
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        return candidate


@pytest.fixture
async def application(
    published_job: Job, candidate_profile: CandidateProfile
) -> Application:
    """Create a NEW application linking a candidate to a published job."""
    async with TestSessionLocal() as session:
        app_obj = Application(
            job_id=published_job.id,
            candidate_id=candidate_profile.id,
            status=ApplicationStatus.NEW,
        )
        session.add(app_obj)
        await session.commit()
        await session.refresh(app_obj)
        return app_obj


# ==================== API Client Fixtures ====================


async def override_get_session():
    """Override get_session dependency for tests."""
    async with TestSessionLocal() as session:
        yield session


def _apply_admin_overrides(admin_user: User) -> None:
    async def _current_user(
        credentials=None,  # noqa: ARG001
        session=None,  # noqa: ARG001
    ):
        return admin_user

    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_current_admin] = _current_user


def _apply_company_overrides(company_user: User) -> None:
    async def _current_company():
        async with TestSessionLocal() as session:
            user = (
                await session.execute(
                    select(User).where(User.id == company_user.id)  # pyright: ignore[reportArgumentType]
                )
            ).scalar_one()
            company_profile = (
                await session.execute(
                    select(CompanyProfile).where(  # pyright: ignore[reportArgumentType]
                        CompanyProfile.user_id == user.id
                    )
                )
            ).scalar_one()
            return (user, company_profile)

    app.dependency_overrides[get_current_company] = _current_company


async def _make_client() -> AsyncGenerator[AsyncClient, None]:
    """Yield an AsyncClient bound to the FastAPI app under test.

    Caller is responsible for setting any auth dependency overrides BEFORE
    awaiting this generator's first yield, and the fixture wrapper handles
    tearing them down afterwards.
    """
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def company_client(
    approved_company_user: User,
) -> AsyncGenerator[AsyncClient, None]:
    """Test client authenticated as a company user."""
    _apply_company_overrides(approved_company_user)
    async for client in _make_client():
        yield client


@pytest.fixture
async def admin_client(admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    """Test client authenticated as an admin user."""
    _apply_admin_overrides(admin_user)
    async for client in _make_client():
        yield client


@pytest.fixture
async def public_client() -> AsyncGenerator[AsyncClient, None]:
    """Test client without authentication (for public endpoints)."""
    async for client in _make_client():
        yield client


# Legacy alias for backward compatibility
@pytest.fixture
async def client(company_client: AsyncClient) -> AsyncClient:
    """Legacy alias for company_client."""
    return company_client


@pytest.fixture
async def unauthenticated_client(test_db) -> AsyncGenerator[AsyncClient, None]:
    """Client with no auth dependency overrides.

    Use to verify protected endpoints return 401 when called without a token.
    The session override IS applied so the request reaches the auth guard
    instead of failing at DB acquisition.
    """
    app.dependency_overrides.clear()
    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
