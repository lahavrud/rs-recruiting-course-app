"""Database configuration and async engine setup."""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.infrastructure.config import settings

# Import models to ensure they're registered with SQLModel.metadata
from src.models import SQLModel  # noqa: F401

logger = logging.getLogger(__name__)

# Idempotent ALTER TABLE statements for columns added after initial schema creation.
# Each entry is applied at startup; errors are swallowed so they are safe to re-run.
_MIGRATIONS: list[str] = [
    "ALTER TABLE companyprofile ADD COLUMN address TEXT",
    "ALTER TABLE companyprofile ADD COLUMN privacy_accepted_at DATETIME",
]

# Database URL - uses config which reads from environment variables
DATABASE_URL = settings.database_url

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    # Log SQL queries (configurable via DATABASE_ECHO env var)
    echo=settings.database_echo,
    future=True,
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize database tables and apply lightweight column migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass  # Column already exists — safe to ignore


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session."""
    async with async_session() as session:
        yield session
