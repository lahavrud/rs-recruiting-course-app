"""Async transaction context manager for FastAPI + SQLAlchemy write endpoints."""

import contextvars
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

_post_commit_hooks: contextvars.ContextVar[
    list[Callable[[], Awaitable[None]]] | None
] = contextvars.ContextVar("_post_commit_hooks", default=None)


def defer_after_commit(fn: Callable[[], Awaitable[None]]) -> None:
    """Register an async callable to run after the current transaction commits.

    Must be called from within a `transactional()` block.  If the transaction
    rolls back, registered functions are discarded and never called.

    Raises RuntimeError when called outside of a transactional() context.
    """
    hooks = _post_commit_hooks.get()
    if hooks is None:
        raise RuntimeError("defer_after_commit() called outside of transactional()")
    hooks.append(fn)


@asynccontextmanager
async def transactional(session: AsyncSession) -> AsyncGenerator[None, None]:
    """Commit on success; rollback and re-raise on any exception.

    Side effects (emails, file uploads) registered via defer_after_commit()
    are run after the commit succeeds and are silently dropped on rollback.

    Usage in API endpoints::

        try:
            async with transactional(session):
                result = await some_service(...)
        except DomainError as e:
            raise service_exception_to_http(e) from e

    The context manager owns the commit/rollback; the endpoint's except
    block only needs to handle HTTP mapping of domain exceptions.
    """
    hooks: list[Callable[[], Awaitable[None]]] = []
    token = _post_commit_hooks.set(hooks)
    try:
        yield
        await session.commit()
        for hook in hooks:
            await hook()
    except Exception:
        await session.rollback()
        raise
    finally:
        _post_commit_hooks.reset(token)
