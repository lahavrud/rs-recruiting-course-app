"""Tests for email service."""

from unittest.mock import AsyncMock, patch

import pytest

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.services.email import (
    SESEmailProvider,
    SMTPEmailProvider,
    get_email_provider,
)


class TestSMTPEmailProvider:
    """Tests for SMTPEmailProvider."""

    @pytest.fixture
    def provider(self):
        """Create an SMTPEmailProvider instance."""
        return SMTPEmailProvider(
            smtp_host="localhost",
            smtp_port=587,
            smtp_user="test@example.com",
            smtp_password="password",
            from_email="sender@example.com",
            use_tls=True,
        )

    @pytest.mark.asyncio
    @patch("rs_shared.core.services.email.aiosmtplib.send", new_callable=AsyncMock)
    async def test_send_email_success(self, mock_send, provider: SMTPEmailProvider):
        """Test successful email sending via SMTP."""
        result = await provider.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        mock_send.assert_awaited_once()
        kwargs = mock_send.await_args.kwargs
        assert kwargs["hostname"] == "localhost"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "test@example.com"
        assert kwargs["password"] == "password"
        assert kwargs["start_tls"] is True
        assert kwargs["timeout"] == 30

    @pytest.mark.asyncio
    @patch("rs_shared.core.services.email.aiosmtplib.send", new_callable=AsyncMock)
    async def test_send_email_multiple_recipients(
        self, mock_send, provider: SMTPEmailProvider
    ):
        """Test sending email to multiple recipients."""
        result = await provider.send_email(
            to=["recipient1@example.com", "recipient2@example.com"],
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        mock_send.assert_awaited_once()
        msg = mock_send.await_args.args[0]
        assert "recipient1@example.com" in msg["To"]
        assert "recipient2@example.com" in msg["To"]

    @pytest.mark.asyncio
    @patch("rs_shared.core.services.email.aiosmtplib.send", new_callable=AsyncMock)
    async def test_send_email_without_auth(self, mock_send):
        """Test sending email without authentication."""
        provider = SMTPEmailProvider(
            smtp_host="localhost",
            smtp_port=587,
            from_email="sender@example.com",
            use_tls=True,
        )

        result = await provider.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert result is True
        kwargs = mock_send.await_args.kwargs
        assert kwargs["username"] is None
        assert kwargs["password"] is None

    @pytest.mark.asyncio
    @patch("rs_shared.core.services.email.aiosmtplib.send", new_callable=AsyncMock)
    async def test_send_email_failure(self, mock_send, provider: SMTPEmailProvider):
        """Test email sending failure."""
        mock_send.side_effect = Exception("SMTP error")

        result = await provider.send_email(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test Body",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_email_no_sender(self):
        """Test sending email without sender configured."""
        provider = SMTPEmailProvider(
            smtp_host="localhost",
            smtp_port=587,
            use_tls=True,
        )

        with pytest.raises(ValueError, match="No sender email address configured"):
            await provider.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )


class TestSESEmailProvider:
    """Tests for SESEmailProvider."""

    @pytest.fixture
    def provider(self):
        """Create an SESEmailProvider instance."""
        return SESEmailProvider(
            region="us-east-1",
            from_email="sender@example.com",
            access_key_id="test-key",
            secret_access_key="test-secret",
        )

    @pytest.mark.asyncio
    async def test_send_email_success(self, provider: SESEmailProvider):
        """Test successful email sending via SES."""
        with patch.object(provider.session, "client") as mock_client:
            mock_ses = AsyncMock()
            mock_ses.send_email = AsyncMock(return_value={})
            mock_client.return_value.__aenter__.return_value = mock_ses

            result = await provider.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            assert result is True
            mock_ses.send_email.assert_called_once()
            call_args = mock_ses.send_email.call_args[1]
            assert call_args["Source"] == "sender@example.com"
            assert call_args["Destination"]["ToAddresses"] == ["recipient@example.com"]
            assert call_args["Message"]["Subject"]["Data"] == "Test Subject"

    @pytest.mark.asyncio
    async def test_send_email_multiple_recipients(self, provider: SESEmailProvider):
        """Test sending email to multiple recipients via SES."""
        with patch.object(provider.session, "client") as mock_client:
            mock_ses = AsyncMock()
            mock_ses.send_email = AsyncMock(return_value={})
            mock_client.return_value.__aenter__.return_value = mock_ses

            result = await provider.send_email(
                to=["recipient1@example.com", "recipient2@example.com"],
                subject="Test Subject",
                body="Test Body",
            )

            assert result is True
            call_args = mock_ses.send_email.call_args[1]
            assert len(call_args["Destination"]["ToAddresses"]) == 2

    @pytest.mark.asyncio
    async def test_send_email_with_custom_from(self, provider: SESEmailProvider):
        """Test sending email with custom from address."""
        with patch.object(provider.session, "client") as mock_client:
            mock_ses = AsyncMock()
            mock_ses.send_email = AsyncMock(return_value={})
            mock_client.return_value.__aenter__.return_value = mock_ses

            result = await provider.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
                from_email="custom@example.com",
            )

            assert result is True
            call_args = mock_ses.send_email.call_args[1]
            assert call_args["Source"] == "custom@example.com"

    @pytest.mark.asyncio
    async def test_send_email_failure(self, provider: SESEmailProvider):
        """Test email sending failure via SES."""
        from botocore.exceptions import ClientError

        with patch.object(provider.session, "client") as mock_client:
            mock_ses = AsyncMock()
            error_response = {"Error": {"Code": "MessageRejected"}}
            mock_ses.send_email = AsyncMock(
                side_effect=ClientError(error_response, "SendEmail")
            )
            mock_client.return_value.__aenter__.return_value = mock_ses

            result = await provider.send_email(
                to="recipient@example.com",
                subject="Test Subject",
                body="Test Body",
            )

            assert result is False


class TestEmailProviderFactory:
    """Tests for email provider factory function."""

    def test_get_email_provider_smtp(self, monkeypatch):
        """Test getting SMTP email provider."""
        monkeypatch.setattr(settings, "email_provider", "smtp")
        monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
        monkeypatch.setattr(settings, "smtp_port", 587)  # Use int, not string
        monkeypatch.setattr(settings, "smtp_user", "user@example.com")
        monkeypatch.setattr(settings, "smtp_password", "password")
        monkeypatch.setattr(settings, "smtp_from_email", "sender@example.com")

        provider = get_email_provider()
        assert isinstance(provider, SMTPEmailProvider)
        assert provider.smtp_host == "smtp.example.com"

    def test_get_email_provider_ses(self, monkeypatch):
        """Test getting SES email provider."""
        monkeypatch.setattr(settings, "email_provider", "ses")
        monkeypatch.setattr(settings, "aws_region", "us-east-1")
        monkeypatch.setattr(settings, "aws_ses_from_email", "sender@example.com")

        provider = get_email_provider()
        assert isinstance(provider, SESEmailProvider)
        assert provider.from_email == "sender@example.com"

    def test_get_email_provider_ses_missing_from_email(self, monkeypatch):
        """Test SES provider requires from email."""
        monkeypatch.setattr(settings, "email_provider", "ses")
        monkeypatch.setattr(settings, "aws_ses_from_email", None)

        with pytest.raises(ValueError, match="AWS_SES_FROM_EMAIL must be set"):
            get_email_provider()
