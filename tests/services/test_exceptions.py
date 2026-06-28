"""Unit tests for custom exception classes."""

import pytest

from rs_shared.services.exceptions import (
    AuthError,
    EmailAlreadyExistsError,
)


class TestEmailAlreadyExistsError:
    """Tests for EmailAlreadyExistsError — pins non-obvious custom __init__ behavior."""

    def test_email_already_exists_error_message_includes_email(self):
        """Test that exception message includes email."""
        email = "test@example.com"
        error = EmailAlreadyExistsError(email)

        assert email in str(error)
        assert "already registered" in str(error).lower()

    def test_email_already_exists_error_email_attribute(self):
        """Test that email attribute is set correctly."""
        email = "user@example.com"
        error = EmailAlreadyExistsError(email)

        assert error.email == email

    def test_email_already_exists_error_can_be_raised_and_caught(self):
        """Test that exception can be raised and caught."""
        email = "test@example.com"

        with pytest.raises(EmailAlreadyExistsError) as exc_info:
            raise EmailAlreadyExistsError(email)

        assert exc_info.value.email == email
        assert email in str(exc_info.value)

    def test_email_already_exists_error_can_be_caught_as_auth_error(self):
        """Test that exception can be caught as AuthError."""
        email = "test@example.com"

        with pytest.raises(AuthError):
            raise EmailAlreadyExistsError(email)
