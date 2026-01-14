"""Email service abstraction layer for email providers."""

import asyncio
import logging
import smtplib
from abc import ABC, abstractmethod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

import aioboto3
from botocore.exceptions import ClientError
from email_validator import EmailNotValidError, validate_email

from src.core.config import settings

logger = logging.getLogger(__name__)


class EmailProvider(ABC):
    """Abstract base class for email providers."""

    @abstractmethod
    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to: Recipient email address(es)
            subject: Email subject
            body: Email body (plain text)
            from_email: Sender email address (optional, uses default if not provided)

        Returns:
            True if sent successfully, False otherwise
        """
        pass


class SESEmailProvider(EmailProvider):
    """AWS SES email provider implementation."""

    def __init__(
        self,
        region: str,
        from_email: str,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        """
        Initialize SES email provider.

        Args:
            region: AWS region
            from_email: Default sender email address (must be verified in SES)
            access_key_id: AWS access key ID (optional, can use IAM role)
            secret_access_key: AWS secret access key (optional, can use IAM role)
        """
        self.region = region
        self.from_email = from_email
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.session = aioboto3.Session()

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """Send email via AWS SES."""
        # Normalize recipients to list
        recipients = [to] if isinstance(to, str) else to
        sender = from_email or self.from_email

        # Validate email addresses (format only, no DNS check)
        try:
            validate_email(sender, check_deliverability=False)
            for recipient in recipients:
                validate_email(recipient, check_deliverability=False)
        except EmailNotValidError as e:
            logger.error(f"Invalid email address: {e}")
            return False

        async with self.session.client(  # type: ignore[attr-defined]
            "ses",
            region_name=self.region,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        ) as ses:
            try:
                await ses.send_email(
                    Source=sender,
                    Destination={"ToAddresses": recipients},
                    Message={
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                    },
                )
                return True
            except ClientError as e:
                logger.error(f"SES error sending email: {e}")
                return False


class SMTPEmailProvider(EmailProvider):
    """SMTP email provider (for development/testing)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        use_tls: bool = True,
    ):
        """
        Initialize SMTP email provider.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_user: SMTP username (optional)
            smtp_password: SMTP password (optional)
            from_email: Default sender email address
            use_tls: Whether to use TLS encryption
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email or smtp_user
        self.use_tls = use_tls

    def _send_smtp_email_sync(
        self,
        recipients: List[str],
        sender: str,
        subject: str,
        body: str,
    ) -> bool:
        """Synchronous SMTP email sending (runs in executor)."""
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            # Send email via synchronous SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return True
        except Exception as e:
            logger.error(f"SMTP error sending email: {e}")
            return False

    async def send_email(
        self,
        to: str | List[str],
        subject: str,
        body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """Send email via SMTP (non-blocking)."""
        recipients = [to] if isinstance(to, str) else to
        sender = from_email or self.from_email

        if not sender:
            raise ValueError("No sender email address configured")

        # Validate email addresses (format only, no DNS check)
        try:
            validate_email(sender, check_deliverability=False)
            for recipient in recipients:
                validate_email(recipient, check_deliverability=False)
        except EmailNotValidError as e:
            logger.error(f"Invalid email address: {e}")
            return False

        # Run synchronous SMTP operations in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._send_smtp_email_sync, recipients, sender, subject, body
        )


def get_email_provider() -> EmailProvider:
    """
    Factory function to get email provider based on configuration.

    Returns:
        EmailProvider instance configured from settings
    """
    if settings.email_provider == "ses":
        if not settings.aws_ses_from_email:
            raise ValueError("AWS_SES_FROM_EMAIL must be set when using SES")
        return SESEmailProvider(
            region=settings.aws_region,
            from_email=settings.aws_ses_from_email,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
        )
    else:  # smtp
        return SMTPEmailProvider(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            use_tls=settings.smtp_use_tls,
        )
