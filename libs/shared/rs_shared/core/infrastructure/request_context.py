"""Request-correlation logging primitives — framework-free.

Holds the `request_id` ContextVar and the logging filter that stamps it onto
every LogRecord. Kept separate from `middleware.py` (which carries the
Starlette `RequestMiddleware`) so both the API *and* the SQS worker can install
the filter without importing the web stack — the worker logs with an empty
request_id since it never serves HTTP requests.
"""

import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class RequestIdFilter(logging.Filter):
    """Inject the current request_id into every LogRecord emitted in this context.

    Install once on the root logger so every logger in the process picks it up.
    When called outside a request context the field is an empty string.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("")  # type: ignore[attr-defined]  # dynamically attaching request_id to LogRecord; stdlib stubs don't declare it
        return True
