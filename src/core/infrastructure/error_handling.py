"""Error handling utilities for converting service exceptions to HTTP exceptions."""

from fastapi import HTTPException, status

from src.services.exceptions import (
    AccountLockedError,
    ApplicationAlreadyExistsError,
    ApplicationNotFoundError,
    CompanyNotFoundError,
    CompanyNotPendingError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidActivationTokenError,
    InvalidApplicationStatusTransitionError,
    InvalidCredentialsError,
    InvalidInviteTokenError,
    InviteAlreadyRevokedError,
    InviteNotFoundError,
    InvitePendingForEmailError,
    JobCannotBeDeletedError,
    JobCannotBeUpdatedError,
    JobNotFoundError,
    JobNotOwnedByCompanyError,
    JobNotPendingError,
    PendingActivationError,
    PendingApprovalError,
)

# Mapping of service exceptions to HTTP status codes
EXCEPTION_STATUS_MAP: dict[type[Exception], int] = {
    # Not found errors (404)
    JobNotFoundError: status.HTTP_404_NOT_FOUND,
    CompanyNotFoundError: status.HTTP_404_NOT_FOUND,
    ApplicationNotFoundError: status.HTTP_404_NOT_FOUND,
    # Conflict errors (409)
    ApplicationAlreadyExistsError: status.HTTP_409_CONFLICT,
    InvitePendingForEmailError: status.HTTP_409_CONFLICT,
    EmailAlreadyExistsError: status.HTTP_409_CONFLICT,
    # Forbidden errors (403)
    JobNotOwnedByCompanyError: status.HTTP_403_FORBIDDEN,
    InactiveUserError: status.HTTP_403_FORBIDDEN,
    PendingApprovalError: status.HTTP_403_FORBIDDEN,
    PendingActivationError: status.HTTP_403_FORBIDDEN,
    # Bad request — invalid activation token
    InvalidActivationTokenError: status.HTTP_400_BAD_REQUEST,
    # Unauthorized errors (401)
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    # Too many requests (429)
    AccountLockedError: status.HTTP_429_TOO_MANY_REQUESTS,
    # Bad request errors (400)
    InvalidInviteTokenError: status.HTTP_400_BAD_REQUEST,
    InviteAlreadyRevokedError: status.HTTP_400_BAD_REQUEST,
    # Not found (404)
    InviteNotFoundError: status.HTTP_404_NOT_FOUND,
    JobCannotBeUpdatedError: status.HTTP_400_BAD_REQUEST,
    JobCannotBeDeletedError: status.HTTP_400_BAD_REQUEST,
    CompanyNotPendingError: status.HTTP_400_BAD_REQUEST,
    JobNotPendingError: status.HTTP_400_BAD_REQUEST,
    InvalidApplicationStatusTransitionError: status.HTTP_400_BAD_REQUEST,
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
