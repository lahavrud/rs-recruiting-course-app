"""Account activation endpoint (company + candidate)."""

import logging

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.infrastructure.config import settings
from src.core.infrastructure.database import get_session
from src.core.infrastructure.dependencies import client_ip
from src.core.infrastructure.error_handling import service_exception_to_http
from src.core.infrastructure.limiter import get_limiter
from src.core.infrastructure.transactions import defer_after_commit, transactional
from src.core.tasks import enqueue_email_task
from src.enums import UserRole
from src.services.auth.activation import activate_user
from src.services.exceptions import InvalidActivationTokenError
from src.templates.email import build_candidate_welcome_html

logger = logging.getLogger(__name__)
limiter = get_limiter()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/activate", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
async def activate(
    request: Request,
    token: str = Query(
        ..., description="One-time activation token from the activation email"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Activate a user account (company or candidate) using the one-time token.

    Dispatches by role inside `activate_user`; for candidates this also
    creates / links their CandidateProfile and records consent.
    """
    try:
        async with transactional(session):
            user = await activate_user(
                token,
                session,
                ip_address=client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )

            # Candidate-only: schedule the post-activation explainer email
            # after the transaction commits. MUST register the hook from
            # *inside* the transactional() block — once the context exits
            # the post-commit hooks contextvar is reset to None, and a
            # late call to defer_after_commit() raises RuntimeError. That
            # turns a successful activation (token already used,
            # is_active=True) into a 500 to the client, which then sees a
            # "token invalid" toast and retries registration, hitting 409
            # because the user is actually active. Company welcomes are
            # handled by the existing approval-email flow.
            if user.role == UserRole.CANDIDATE:
                candidate_email = user.email
                # The candidate's session isn't authenticated when they
                # open the welcome email; route every CTA through
                # /login?redirect=... so the next click lands on a sign-in
                # screen and forwards to the intended destination after
                # the credential flow.
                jobs_url = f"{settings.frontend_base_url}/login?redirect=/jobs"
                profile_url = (
                    f"{settings.frontend_base_url}/login?redirect=/candidate/profile"
                )

                async def _send_welcome() -> None:
                    html = build_candidate_welcome_html(
                        jobs_url=jobs_url, profile_url=profile_url
                    )
                    try:
                        await enqueue_email_task(
                            to=candidate_email,
                            subject="ברוכים הבאים ל-RS Recruiting",
                            body=(
                                "החשבון שלכם הופעל. כעת תוכלו להתחבר ולנהל"
                                " את ההגשות שלכם.\n"
                                f"מועדי משרות פתוחים: {jobs_url}\n"
                                f"פרופיל אישי: {profile_url}\n"
                            ),
                            html_body=html,
                        )
                    except Exception:  # pragma: no cover — best-effort
                        logger.exception("Failed to enqueue candidate welcome email")

                defer_after_commit(_send_welcome)
    except InvalidActivationTokenError as e:
        raise service_exception_to_http(e) from e

    return {"message": "החשבון הופעל בהצלחה"}
