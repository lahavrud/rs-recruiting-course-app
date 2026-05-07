"""Async transaction context manager for FastAPI + SQLAlchemy write endpoints."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transactional(session: AsyncSession) -> AsyncGenerator[None, None]:
    """Commit on success; rollback and re-raise on any exception.

    Usage in API endpoints::

        try:
            async with transactional(session):
                result = await some_service(...)
        except DomainError as e:
            raise service_exception_to_http(e) from e

    The context manager owns the commit/rollback; the endpoint's except
    block only needs to handle HTTP mapping of domain exceptions.
    """
    try:
        yield
        await session.commit()
    except Exception:
        await session.rollback()
        raise
