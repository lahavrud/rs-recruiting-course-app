"""Unit tests for error handling utilities."""

from fastapi import HTTPException, status

from src.core.infrastructure.error_handling import service_exception_to_http
from src.services.exceptions import (
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
    JobNotPendingError,
)


class TestServiceExceptionToHttp:
    """Tests for service_exception_to_http function."""

    def test_job_not_found_error_maps_to_404(self):
        """Test that JobNotFoundError maps to 404."""
        exception = JobNotFoundError("Job not found")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_404_NOT_FOUND
        assert http_exception.detail == "Job not found"

    def test_company_not_found_error_maps_to_404(self):
        """Test that CompanyNotFoundError maps to 404."""
        exception = CompanyNotFoundError("Company not found")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_404_NOT_FOUND
        assert http_exception.detail == "Company not found"

    def test_job_not_owned_by_company_error_maps_to_403(self):
        """Test that JobNotOwnedByCompanyError maps to 403."""
        exception = JobNotOwnedByCompanyError("Job not owned by company")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_403_FORBIDDEN
        assert http_exception.detail == "Job not owned by company"

    def test_inactive_user_error_maps_to_403(self):
        """Test that InactiveUserError maps to 403."""
        exception = InactiveUserError("User is inactive")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_403_FORBIDDEN
        assert http_exception.detail == "User is inactive"

    def test_invalid_credentials_error_maps_to_401(self):
        """Test that InvalidCredentialsError maps to 401."""
        exception = InvalidCredentialsError("Invalid credentials")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_401_UNAUTHORIZED
        assert http_exception.detail == "Invalid credentials"

    def test_job_cannot_be_updated_error_maps_to_400(self):
        """Test that JobCannotBeUpdatedError maps to 400."""
        exception = JobCannotBeUpdatedError("Job cannot be updated")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "Job cannot be updated"

    def test_job_cannot_be_deleted_error_maps_to_400(self):
        """Test that JobCannotBeDeletedError maps to 400."""
        exception = JobCannotBeDeletedError("Job cannot be deleted")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "Job cannot be deleted"

    def test_company_not_pending_error_maps_to_400(self):
        """Test that CompanyNotPendingError maps to 400."""
        exception = CompanyNotPendingError("Company is not pending")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "Company is not pending"

    def test_job_not_pending_error_maps_to_400(self):
        """Test that JobNotPendingError maps to 400."""
        exception = JobNotPendingError("Job is not pending")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        assert http_exception.detail == "Job is not pending"

    def test_email_already_exists_error_maps_to_400(self):
        """Test that EmailAlreadyExistsError maps to 400."""
        exception = EmailAlreadyExistsError("test@example.com")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_400_BAD_REQUEST
        # EmailAlreadyExistsError includes email in message
        assert "test@example.com" in http_exception.detail

    def test_unmapped_exception_uses_default_status(self):
        """Test that unmapped exceptions use default status code."""
        exception = ValueError("Some error")
        http_exception = service_exception_to_http(exception)

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert http_exception.detail == "Some error"

    def test_unmapped_exception_with_custom_default(self):
        """Test that unmapped exceptions can use custom default status."""
        exception = ValueError("Some error")
        custom_status = status.HTTP_418_IM_A_TEAPOT
        http_exception = service_exception_to_http(
            exception, default_status=custom_status
        )

        assert isinstance(http_exception, HTTPException)
        assert http_exception.status_code == custom_status
        assert http_exception.detail == "Some error"

    def test_exception_preserves_message(self):
        """Test that exception message is preserved in HTTPException detail."""
        exception = JobNotFoundError("Custom error message")
        http_exception = service_exception_to_http(exception)

        assert http_exception.detail == "Custom error message"
