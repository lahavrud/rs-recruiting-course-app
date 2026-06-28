"""Async transaction context manager for FastAPI + SQLAlchemy write endpoints."""

import contextvars
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)

_post_commit_hooks: contextvars.ContextVar[
    list[Callable[[], Awaitable[object]]] | None
] = contextvars.ContextVar("_post_commit_hooks", default=None)


def defer_after_commit(fn: Callable[[], Awaitable[object]]) -> None:
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

    Isolation level: PostgreSQL default READ COMMITTED.  This is sufficient
    for the current write patterns (single-row approvals, status updates) where
    each row is owned by one writer at a time.  If a future flow needs
    SERIALIZABLE (e.g. check-then-act on aggregate counts), add an opt-in
    ``isolation`` arg here and set it via
    ``await session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))``
    before the first DML statement.

    Side effects registered via defer_after_commit() run after the commit
    succeeds and are discarded on rollback.  Hook failures are logged but
    never propagate back to the caller or corrupt the HTTP response.

    Usage in API endpoints::

        try:
            async with transactional(session):
                result = await some_service(...)
        except DomainError as e:
            raise service_exception_to_http(e) from e

    The context manager owns the commit/rollback; the endpoint's except
    block only needs to handle HTTP mapping of domain exceptions.
    """
    hooks: list[Callable[[], Awaitable[object]]] = []
    token = _post_commit_hooks.set(hooks)
    committed = False
    try:
        yield
        await session.commit()
        committed = True
    except Exception:
        await session.rollback()
        raise
    finally:
        _post_commit_hooks.reset(token)

    if committed:
        for hook in hooks:
            try:
                await hook()
            except Exception:
                _logger.exception("post-commit hook failed")
