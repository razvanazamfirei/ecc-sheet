"""Tests for email service."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.email_service import generate_csv_content, send_report_email
from backend.models import Resident, Role, TimeEntry, db
from backend.report_utils import generate_csv_content


class TestEmailService:
    """Tests for email service functions."""

    def test_send_report_email_no_credentials(self, app):
        """Test that email fails without credentials."""
        with app.app_context():
            app.config["EMAIL_USERNAME"] = ""
            app.config["EMAIL_PASSWORD"] = ""

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="test@example.com",
            )
            assert result is False

    def test_send_report_email_no_recipient(self, app):
        """Test that email fails without recipient."""
        with app.app_context():
            app.config["EMAIL_USERNAME"] = "test@example.com"
            app.config["EMAIL_PASSWORD"] = "password"
            app.config["EMAIL_RECIPIENT"] = ""

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email=None,
            )
            assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_success(self, mock_config, mock_smtp, app):
        """Test successful email sending with mocked SMTP."""
        with app.app_context():
            # Configure mock
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = "password"
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

    @patch("backend.email_service.smtplib.SMTP")
    @patch("backend.email_service.Config")
    def test_send_report_email_with_resident_filter(self, mock_config, mock_smtp, app, sample_resident):
        """Test email with resident filter."""
        with app.app_context():
            mock_config.EMAIL_USERNAME = "test@example.com"
            mock_config.EMAIL_PASSWORD = "password"
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
    def test_send_report_email_smtp_auth_error(self, mock_smtp, app):
        """Test email with SMTP authentication error."""
        import smtplib

        with app.app_context():
            app.config["EMAIL_USERNAME"] = "test@example.com"
            app.config["EMAIL_PASSWORD"] = "wrong_password"
            app.config["EMAIL_HOST"] = "smtp.example.com"
            app.config["EMAIL_PORT"] = 587

            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Auth failed")
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is False

    @patch("backend.email_service.smtplib.SMTP")
    def test_send_report_email_smtp_error(self, mock_smtp, app):
        """Test email with general SMTP error."""
        import smtplib

        with app.app_context():
            app.config["EMAIL_USERNAME"] = "test@example.com"
            app.config["EMAIL_PASSWORD"] = "password"
            app.config["EMAIL_HOST"] = "smtp.example.com"
            app.config["EMAIL_PORT"] = 587

            mock_smtp.side_effect = smtplib.SMTPException("Connection failed")

            result = send_report_email(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                recipient_email="recipient@example.com",
            )
            assert result is False
