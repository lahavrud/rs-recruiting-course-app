"""Error handling utilities for converting service exceptions to HTTP exceptions."""

from fastapi import HTTPException, status

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

# Mapping of service exceptions to HTTP status codes
EXCEPTION_STATUS_MAP: dict[type[Exception], int] = {
    # Not found errors (404)
    JobNotFoundError: status.HTTP_404_NOT_FOUND,
    CompanyNotFoundError: status.HTTP_404_NOT_FOUND,
    # Forbidden errors (403)
    JobNotOwnedByCompanyError: status.HTTP_403_FORBIDDEN,
    InactiveUserError: status.HTTP_403_FORBIDDEN,
    # Unauthorized errors (401)
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    # Bad request errors (400)
    JobCannotBeUpdatedError: status.HTTP_400_BAD_REQUEST,
    JobCannotBeDeletedError: status.HTTP_400_BAD_REQUEST,
    CompanyNotPendingError: status.HTTP_400_BAD_REQUEST,
    JobNotPendingError: status.HTTP_400_BAD_REQUEST,
    EmailAlreadyExistsError: status.HTTP_400_BAD_REQUEST,
}


def service_exception_to_http(
    exception: Exception,
    default_status: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
) -> HTTPException:
    """Convert service exception to HTTPException.

    Args:
        exception: The service exception to convert
        default_status: HTTP status code to use if exception type is not mapped

    Returns:
        HTTPException with appropriate status code and detail message
    """
    status_code = EXCEPTION_STATUS_MAP.get(type(exception), default_status)
    return HTTPException(status_code=status_code, detail=str(exception))
