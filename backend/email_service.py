import logging
from typing import Any

import resend
from flask import current_app

logger = logging.getLogger(__name__)


def init_email_service(app) -> None:
    """Initialize the email service with the app configuration."""
    resend.api_key = app.config.get("RESEND_API_KEY")


def send_email(
    to: str | list[str],
    subject: str,
    html_content: str,
    from_email: str | None = None,
) -> resend.Emails.SendResponse | Any:
    """
    Send an email using Resend.

    Args:
        to: The recipient(s) email address.
        subject: The email subject.
        html_content: The HTML content of the email.
        from_email: The sender email address. Defaults to app config
            DEFAULT_SENDER_EMAIL.

    Returns:
        The response from the Resend API (e.g., {'id': '...'}) or None if it failed.
    """
    if not resend.api_key:
        logger.warning(
            "RESEND_API_KEY is not set. Email not sent to %s (subject: '%s')",
            to,
            subject,
        )
        return None

    if from_email is None:
        from_email = current_app.config.get(
            "DEFAULT_SENDER_EMAIL", "onboarding@resend.dev"
        )

    to_list: list[str] = [to] if isinstance(to, str) else to

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": to_list,
        "subject": subject,
        "html": html_content,
    }

    try:
        email_response = resend.Emails.send(params)
        logger.info(
            "Email sent successfully: %s", getattr(email_response, "id", "Unknown")
        )
        return email_response
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        return None
