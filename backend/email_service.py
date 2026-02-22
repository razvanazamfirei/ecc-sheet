"""Email service for sending reports with CSV attachments."""

import logging
import smtplib
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_validator import EmailNotValidError, validate_email
from flask import render_template

from .config import Config
from .models import TimeEntry
from .report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_csv_content,
)
from .type_defs import ResidentData, TimeEntries

logger = logging.getLogger("ecc_sheet")


def send_report_email(
    start_date: date,
    end_date: date,
    recipient_email: str | None = None,
    resident_id: int | None = None,
    resident_name: str | None = None,
) -> bool:
    """
    Send overtime report via email with CSV attachment

    Args:
        start_date: Start date for report
        end_date: End date for report
        recipient_email: Email address to send to (uses config default if not provided)
        resident_id: Optional resident ID to filter by
        resident_name: Optional resident name for subject line

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        # Validate email configuration
        if not Config.EMAIL_USERNAME or not Config.EMAIL_PASSWORD:
            logger.error("Email credentials not configured")
            return False

        recipient = recipient_email or Config.EMAIL_RECIPIENT
        if not recipient:
            logger.error("No email recipient configured")
            return False

        # Validate sender and recipient email addresses
        try:
            validate_email(Config.EMAIL_USERNAME, check_deliverability=False)
            validate_email(recipient, check_deliverability=False)
        except EmailNotValidError as e:
            logger.exception("Invalid email address in configuration: %s", e)
            return False

        # Get entries and generate content
        query = build_entries_query(start_date, end_date, resident_id)
        entries: TimeEntries = query.order_by(
            TimeEntry.date, TimeEntry.resident_id
        ).all()
        csv_content: str = generate_csv_content(entries)
        resident_data: ResidentData = aggregate_entries_by_resident(entries)
        total_overtime = sum(data["total_overtime"] for data in resident_data.values())

        # Build HTML content
        html_content = render_template(
            "email_report.html",
            start_date=start_date,
            end_date=end_date,
            resident_data=resident_data,
            resident_name=resident_name,
            total_overtime=total_overtime,
        )

        # Create message
        msg = MIMEMultipart("mixed")
        subject = f"ECC Report - {start_date.strftime('%Y-%m-%d')}"
        if resident_name:
            subject += f" - {resident_name}"

        msg["Subject"] = subject
        msg["From"] = Config.EMAIL_USERNAME
        msg["To"] = recipient

        # Attach HTML body
        html_part = MIMEText(html_content, "html")
        msg.attach(html_part)

        # Attach CSV file
        csv_attachment = MIMEApplication(csv_content.encode("utf-8"), _subtype="csv")
        filename = f"overtime_report_{start_date}_{end_date}"
        if resident_name:
            # Clean resident name for filename (remove special characters)
            clean_name = "".join(c for c in resident_name if c.isalnum() or c in " -_")
            filename += f"_{clean_name.replace(' ', '_')}"
        filename += ".csv"

        csv_attachment.add_header(
            "Content-Disposition", "attachment", filename=filename
        )
        msg.attach(csv_attachment)

        # Send email
        with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT, timeout=30) as server:
            server.starttls()
            server.login(Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info("Report email sent successfully to %s", recipient)
        return True

    except smtplib.SMTPException as e:
        logger.error("SMTP error sending report email: %s", e)
        return False

    except Exception as e:
        logger.error("Error sending report email: %s", e)
        return False
