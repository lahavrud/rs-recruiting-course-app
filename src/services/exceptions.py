"""Custom domain exceptions for service layer."""


class AuthError(Exception):
    """Base exception for authentication-related errors."""

    pass


class EmailAlreadyExistsError(AuthError):
    """Raised when attempting to register with an email that already exists."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"Email {email} is already registered")


class InvalidCredentialsError(AuthError):
    """Raised when login credentials are invalid."""

    pass


class InvalidInviteTokenError(AuthError):
    """Raised when a registration invite token is missing, invalid, or expired."""

    pass


class InactiveUserError(AuthError):
    """Raised when attempting to authenticate an inactive user."""

    pass


class PendingApprovalError(AuthError):
    """Raised when a company user is inactive and awaiting admin approval."""

    pass


class PendingActivationError(AuthError):
    """Raised when the company has not yet clicked the activation link."""

    pass


class InvalidActivationTokenError(AuthError):
    """Raised when an activation token is invalid, expired, or already used."""

    pass


class AccountLockedError(AuthError):
    """Raised when an account is locked after too many failed login attempts."""

    def __init__(self, minutes_remaining: int) -> None:
        self.minutes_remaining = minutes_remaining
        super().__init__(
            f"Account temporarily locked. Try again in {minutes_remaining} minute(s)."
        )


class CompanyNotFoundError(Exception):
    """Raised when a company user is not found."""

    pass


class CompanyNotPendingError(Exception):
    """Raised when attempting to approve/reject a company that is not pending."""

    pass


class JobNotFoundError(Exception):
    """Raised when a job is not found."""

    pass


class JobNotOwnedByCompanyError(Exception):
    """Raised when attempting to modify a job that is not owned by the company."""

    pass


class JobCannotBeDeletedError(Exception):
    """Raised when attempting to delete a job that cannot be deleted."""

    pass


class JobCannotBeUpdatedError(Exception):
    """Raised when attempting to update a job that cannot be updated."""

    pass


class JobNotPendingError(Exception):
    """Raised when attempting to approve/reject a job that is not pending."""

    pass


class ApplicationAlreadyExistsError(Exception):
    """Raised when attempting to create an application that already exists."""

    def __init__(self, job_id: int, candidate_id: int) -> None:
        self.job_id = job_id
        self.candidate_id = candidate_id
        super().__init__(
            f"Application already exists for job {job_id} and candidate {candidate_id}"
        )


class ApplicationNotFoundError(Exception):
    """Raised when an application is not found."""

    pass


class InviteNotFoundError(Exception):
    """Raised when an invite token record is not found."""

    pass


class InviteAlreadyRevokedError(Exception):
    """Raised when attempting to revoke or resend a non-pending invite."""

    pass


class InvitePendingForEmailError(Exception):
    """Raised when a pending invite already exists for the given email."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"A pending invite already exists for {email}")


class InvalidApplicationStatusTransitionError(Exception):
    """Raised when attempting an invalid application status transition."""

    pass
