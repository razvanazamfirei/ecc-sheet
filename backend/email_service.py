import logging
from collections.abc import Mapping
from typing import Any

import resend
from email_validator import EmailNotValidError, validate_email
from flask import current_app

logger = logging.getLogger(__name__)


def init_email_service(app) -> None:
    """Initialize the email service with the app configuration."""
    resend.api_key = app.config.get("RESEND_API_KEY")


def _redacted_address(address: str) -> str:
    """Return a minimally useful, privacy-preserving email representation."""
    _local_part, _, domain = address.strip().partition("@")
    if not domain:
        return "<redacted>"
    return f"<redacted>@{domain}"


def _normalize_email(address: str) -> str:
    """Validate and normalize a single email address."""
    return validate_email(address.strip(), check_deliverability=False).normalized


def send_email(
    to: str | list[str],
    subject: str,
    html_content: str,
    from_email: str | None = None,
) -> resend.Emails.SendResponse | Mapping[str, Any] | None:
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
        recipients = [to] if isinstance(to, str) else to
        logger.warning(
            "RESEND_API_KEY is not set. Email not sent. recipients=%s",
            len(recipients),
        )
        return None

    if from_email is None:
        from_email = (
            current_app.config.get("DEFAULT_SENDER_EMAIL") or "onboarding@resend.dev"
        )

    raw_recipients = [to] if isinstance(to, str) else to

    try:
        normalized_from_email = _normalize_email(from_email)
    except EmailNotValidError:
        logger.warning(
            "Email not sent. invalid sender=%s",
            _redacted_address(from_email),
        )
        return None

    to_list: list[str] = []
    for recipient in raw_recipients:
        try:
            to_list.append(_normalize_email(recipient))
        except EmailNotValidError:
            logger.warning(
                "Email not sent. invalid recipient=%s recipients=%s",
                _redacted_address(recipient),
                len(raw_recipients),
            )
            return None

    if not to_list:
        logger.warning("Email not sent. recipients=0")
        return None

    params: resend.Emails.SendParams = {
        "from": normalized_from_email,
        "to": to_list,
        "subject": subject,
        "html": html_content,
    }

    try:
        email_response = resend.Emails.send(params)
        response_id = (
            email_response.get("id")
            if isinstance(email_response, Mapping)
            else getattr(email_response, "id", "Unknown")
        )
        logger.info(
            "Email sent successfully. response_id=%s recipients=%s",
            response_id,
            len(to_list),
        )
        return email_response
    except Exception:
        logger.exception(
            "Failed to send email. recipients=%s first_recipient=%s",
            len(to_list),
            _redacted_address(to_list[0]) if to_list else "<redacted>",
        )
        return None
