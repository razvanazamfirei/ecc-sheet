"""Tests for email service."""

import smtplib
from datetime import date
from unittest.mock import MagicMock, patch

from backend.email_service import send_report_email


class TestEmailService:
    """Tests for email service functions."""

    @patch("backend.email_service.Config")
    def test_send_report_email_no_credentials(self, mock_config, app):
        """Test that email fails without credentials."""
        mock_config.EMAIL_USERNAME = ""
        mock_config.EMAIL_PASSWORD = ""

        with app.app_context():
            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="test@example.com",
            )
            assert result is False

    @patch("backend.email_service.Config")
    def test_send_report_email_no_recipient(self, mock_config, app):
        """Test that email fails without recipient."""
        credential_value = "mail-credential"
        mock_config.EMAIL_USERNAME = "test@example.com"
        mock_config.EMAIL_PASSWORD = credential_value
        mock_config.EMAIL_RECIPIENT = None

        with app.app_context():
            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email=None,
            )
            assert result is False

    # noinspection DuplicatedCode
    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_success(self, mock_config, mock_smtp, app):
        """Test successful email sending with mocked SMTP."""
        with app.app_context():
            credential_value = "mail-credential"
            # Configure mock
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "default@example.com"

            # Setup SMTP mock as context manager
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is True

    # noinspection DuplicatedCode
    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_with_resident_filter(
        self, mock_config, mock_smtp, app, sample_resident
    ):
        """Test email with resident filter."""
        with app.app_context():
            credential_value = "mail-credential"
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "default@example.com"

            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
                resident_id=sample_resident.id,
                resident_name=sample_resident.name,
            )
            assert result is True

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_smtp_auth_error(self, mock_config, mock_smtp, app):
        """Test email with SMTP authentication error."""
        with app.app_context():
            credential_value = "mail-auth-failure"
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "default@example.com"

            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Auth failed"
            )
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_smtp_error(self, mock_config, mock_smtp, app):
        """Test email with general SMTP error."""
        with app.app_context():
            credential_value = "mail-credential"
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "default@example.com"

            mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_general_exception(self, mock_config, mock_smtp, app):
        """Test email with general exception."""
        with app.app_context():
            credential_value = "mail-credential"
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "default@example.com"

            # Simulate a general exception during email building
            mock_smtp.side_effect = Exception("Unexpected error")

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is False

    @patch("backend.email_service.Config")
    def test_send_report_email_no_recipient_and_no_config(self, mock_config, app):
        """Test email fails when no recipient provided and no config default."""
        credential_value = "mail-credential"
        mock_config.EMAIL_USERNAME = "test@example.com"
        mock_config.EMAIL_PASSWORD = credential_value
        mock_config.EMAIL_RECIPIENT = ""

        with app.app_context():
            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email=None,
            )
            assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_uses_config_recipient(self, mock_config, mock_smtp, app):
        """Test email uses config recipient when none provided."""
        with app.app_context():
            credential_value = "mail-credential"
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = credential_value
            mock_config.EMAIL_HOST = "smtp.example.com"
            mock_config.EMAIL_PORT = 587
            mock_config.EMAIL_RECIPIENT = "config-default@example.com"

            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email=None,  # No recipient - should use config default
            )
            assert result is True
