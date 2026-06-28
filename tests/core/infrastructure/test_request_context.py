"""Tests for the framework-free request-correlation logging primitives."""

import logging

from src.core.infrastructure.request_context import RequestIdFilter, request_id_var


def test_request_id_filter_injects_field():
    """RequestIdFilter adds request_id to every LogRecord."""
    token = request_id_var.set("test-uuid-1234")
    try:
        f = RequestIdFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f.filter(record)
        assert record.__dict__["request_id"] == "test-uuid-1234"
    finally:
        request_id_var.reset(token)


def test_request_id_filter_empty_outside_request():
    """Outside a request context, request_id is an empty string."""
    f = RequestIdFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello",
        args=(),
        exc_info=None,
    )
    f.filter(record)
    assert record.__dict__["request_id"] == ""
