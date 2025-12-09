import smtplib
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import Config
from ..models import DailySheet, TimeEntry, db
from ..utils import philly_now, philly_today


def send_daily_email(app):
    """Send daily email with completed ECC sheet data"""
    with app.app_context():
        yesterday = philly_today() - timedelta(days=1)

        # Get the daily sheet for yesterday
        daily_sheet = DailySheet.query.filter_by(date=yesterday).first()

        if not daily_sheet:
            print(f"No sheet found for {yesterday}")
            return

        # Get all time entries for yesterday
        entries = TimeEntry.query.filter_by(date=yesterday).order_by(TimeEntry.id).all()

        if not entries:
            print(f"No entries found for {yesterday}")
            return

        # Build email content
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
                <h2>ECC Sheet - {yesterday.strftime("%B %d, %Y")}</h2>
                <p>Status: {"Locked" if daily_sheet.locked else "Unlocked"}</p>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Role</th>
                        <th>Name</th>
                        <th>Exit Time</th>
                        <th>Overtime Hours</th>
                        <th>Airway Assist</th>
                        <th>Emergency</th>
                        <th>Dinner Break</th>
                        <th>Paper Record</th>
                    </tr>
                </thead>
                <tbody>
        """

        total_overtime = 0.0

        for entry in entries:
            overtime = entry.calculate_overtime_hours()
            total_overtime += overtime
            exit_time_str = (
                entry.exit_time.strftime("%H:%M") if entry.exit_time else "-"
            )

            html_content += f"""
                    <tr>
                        <td>{entry.role.name}</td>
                        <td>{entry.resident.name}</td>
                        <td>{exit_time_str}</td>
                        <td class="overtime">{overtime:.2f}</td>
                        <td>{"✓" if entry.airway_assist else ""}</td>
                        <td>{"✓" if entry.emergency else ""}</td>
                        <td>{"✓" if entry.dinner_break else ""}</td>
                        <td>{"✓" if entry.paper_record else ""}</td>
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

        # Send email
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"ECC Sheet - {yesterday.strftime('%B %d, %Y')}"
            msg["From"] = Config.EMAIL_USERNAME
            msg["To"] = Config.EMAIL_RECIPIENT

            html_part = MIMEText(html_content, "html")
            msg.attach(html_part)

            with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT) as server:
                server.starttls()
                server.login(Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD)
                server.send_message(msg)

            # Mark as submitted
            daily_sheet.submitted = True
            daily_sheet.submitted_at = philly_now()
            db.session.commit()

            print(f"Email sent successfully for {yesterday}")

        except Exception as e:
            print(f"Error sending email: {e!s}")


def start_scheduler(app):
    """Start the background scheduler for daily emails"""
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
    )

    scheduler.start()
    print("Scheduler started - Daily emails will be sent at 5:00 AM")

    return scheduler
