from unittest.mock import patch

import pytest
import resend

from backend.email_service import init_email_service, send_email


@pytest.fixture
def app_context_with_resend(app):
    with app.app_context():
        app.config["RESEND_API_KEY"] = "re_test_12345"
        app.config["DEFAULT_SENDER_EMAIL"] = "test@example.com"
        init_email_service(app)
        yield app


class TestEmailService:
    def test_init_email_service(self, app_context_with_resend):
        assert resend.api_key == "re_test_12345"

    @patch("resend.Emails.send")
    def test_send_email_success(self, mock_send, app_context_with_resend):
        mock_send.return_value = {"id": "re_1234"}

        result = send_email(
            to="user@test.com",
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
        )

        assert result == {"id": "re_1234"}
        mock_send.assert_called_once_with(
            {
                "from": "test@example.com",
                "to": ["user@test.com"],
                "subject": "Test Subject",
                "html": "<p>Test HTML</p>",
            }
        )

    def test_send_email_no_api_key(self, app_context_with_resend):
        # Temporarily unset the API key
        resend.api_key = None
        result = send_email(
            to="user@test.com",
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
        )
        assert result is None

    @patch("resend.Emails.send")
    def test_send_email_failure(self, mock_send, app_context_with_resend):
        mock_send.side_effect = Exception("API Error")

        result = send_email(
            to="user@test.com",
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
        )

        assert result is None
