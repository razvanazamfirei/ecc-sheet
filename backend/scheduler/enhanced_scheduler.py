"""
Enhanced scheduler with retry logic and error handling
"""

import logging
import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from time import sleep

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import Config
from ..models import DailySheet, TimeEntry, db
from ..utils import backup_database, philly_now, philly_today

logger = logging.getLogger("ecc_sheet")


def send_daily_email(app, max_retries=3):
    """Send daily email with retry logic"""
    with app.app_context():
        yesterday = philly_today() - timedelta(days=1)

        # Get the daily sheet for yesterday
        daily_sheet = DailySheet.query.filter_by(date=yesterday).first()

        if not daily_sheet:
            logger.info("No sheet found for %s", yesterday)
            return None

        # Get all time entries for yesterday
        entries = TimeEntry.query.filter_by(date=yesterday).order_by(TimeEntry.id).all()

        if not entries:
            logger.info("No entries found for %s", yesterday)
            return None

        html_content = build_email_content(yesterday, daily_sheet, entries)

        # Retry logic for sending email
        for attempt in range(max_retries):
            try:
                send_email(yesterday, html_content)

                # Mark as submitted
                daily_sheet.submitted = True
                daily_sheet.submitted_at = philly_now()
                db.session.commit()

                logger.info("Email sent successfully for %s", yesterday)
                return True

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Authentication failed: {e!s}")  # noqa: G004
                break  # Don't retry auth errors

            except smtplib.SMTPException as e:
                logger.error(
                    "SMTP error on attempt %s/%s: %s", attempt + 1, max_retries, e
                )
                if attempt < max_retries - 1:
                    sleep(60 * (attempt + 1))  # Exponential backoff

            except Exception as e:
                logger.error(
                    "Unexpected error on attempt %s/%s: %s", attempt + 1, max_retries, e
                )
                if attempt < max_retries - 1:
                    sleep(60 * (attempt + 1))

        logger.error("Failed to send email after %s attempts", max_retries)
        return False


def build_email_content(date_obj, daily_sheet, entries):
    """Build HTML email content"""
    html_content = f"""
    <html>
    <head>
        <style>
            table {{
                border-collapse: collapse;
                width: 100%;
                font-family: Arial, sans-serif;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
                text-align: left;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
            }}
            tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            .overtime {{
                font-weight: bold;
                color: #d32f2f;
            }}
            .header {{
                margin-bottom: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>ECC Sheet - {date_obj.strftime("%B %d, %Y")}</h2>
            <p>Status: {"Locked" if daily_sheet.locked else "Unlocked"}</p>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Role</th>
                    <th>Name</th>
                    <th>Exit Time</th>
                    <th>Overtime Hours</th>
                </tr>
            </thead>
            <tbody>
    """

    total_overtime = 0.0

    for entry in entries:
        overtime = entry.calculate_overtime_hours()
        total_overtime += overtime
        exit_time_str = entry.exit_time.strftime("%H:%M") if entry.exit_time else "-"

        html_content += f"""
                <tr>
                    <td>{entry.role.name}</td>
                    <td>{entry.resident.name}</td>
                    <td>{exit_time_str}</td>
                    <td class="overtime">{overtime:.2f}</td>
                </tr>
        """

    html_content += f"""
            </tbody>
            <tfoot>
                <tr>
                    <td colspan="3"><strong>Total Overtime Hours:</strong></td>
                    <td class="overtime"><strong>{total_overtime:.2f}</strong></td>
                    <td colspan="4"></td>
                </tr>
            </tfoot>
        </table>
    </body>
    </html>
    """

    return html_content


def send_email(date_obj, html_content):
    """Send email via SMTP"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"ECC Sheet - {date_obj.strftime('%B %d, %Y')}"
    msg["From"] = Config.EMAIL_USERNAME
    msg["To"] = Config.EMAIL_RECIPIENT

    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT, timeout=30) as server:
        server.starttls()
        server.login(Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD)
        server.send_message(msg)


def start_scheduler(app):
    """Start the background scheduler with error handling"""
    scheduler = BackgroundScheduler()

    # Get timezone from config
    tz = pytz.timezone(Config.TIMEZONE)

    # Schedule daily email at 5 AM
    scheduler.add_job(
        func=lambda: send_daily_email(app),
        trigger=CronTrigger(hour=5, minute=0, timezone=tz),
        id="daily_email",
        name="Send daily ECC sheet email",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,  # Allow 1 hour grace period
    )

    # Schedule daily database backup at 2 AM
    scheduler.add_job(
        func=backup_database_job,
        trigger=CronTrigger(hour=2, minute=0, timezone=tz),
        id="daily_backup",
        name="Backup database",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    logger.info("Scheduler started - Daily emails at 5:00 AM, backups at 2:00 AM")

    return scheduler


def backup_database_job():
    """Job to backup database"""
    success = backup_database()
    if success:
        logger.info("Database backup completed successfully")
    else:
        logger.error("Database backup failed")
