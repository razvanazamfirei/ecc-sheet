"""
Email service for sending reports with CSV attachments
"""
import csv
import logging
import smtplib
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO

from .config import Config
from .models import TimeEntry

logger = logging.getLogger("ecc_sheet")


def generate_csv_report(start_date: date, end_date: date, resident_id: int = None) -> str:
    """
    Generate CSV report for date range

    Args:
        start_date: Start date for report
        end_date: End date for report
        resident_id: Optional resident ID to filter by

    Returns:
        CSV string content
    """
    # Build query for time entries
    query = TimeEntry.query.filter(
        TimeEntry.date >= start_date, TimeEntry.date <= end_date
    )

    # Filter by resident if specified
    if resident_id:
        query = query.filter(TimeEntry.resident_id == resident_id)

    entries = query.order_by(TimeEntry.date, TimeEntry.resident_id).all()

    # Generate CSV
    output = StringIO()
    csv_writer = csv.writer(output)

    # Write header
    csv_writer.writerow(["Date", "Resident", "Role", "Exit Time", "Overtime Hours"])

    # Write data rows
    for entry in entries:
        csv_writer.writerow(
            [
                entry.date.strftime("%Y-%m-%d"),
                entry.resident.name,
                entry.role.name,
                entry.exit_time.strftime("%H:%M") if entry.exit_time else "",
                f"{entry.calculate_overtime_hours():.2f}",
            ]
        )

    return output.getvalue()


def build_report_email_html(
    start_date: date,
    end_date: date,
    resident_data: dict,
    resident_name: str = None,
) -> str:
    """
    Build HTML email content for report

    Args:
        start_date: Start date for report
        end_date: End date for report
        resident_data: Dictionary of resident data with entries and totals
        resident_name: Optional resident name if filtered

    Returns:
        HTML string content
    """
    html_content = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .header {{
                background-color: #4CAF50;
                color: white;
                padding: 20px;
                margin-bottom: 20px;
            }}
            .summary {{
                background-color: #f5f5f5;
                padding: 15px;
                margin-bottom: 20px;
                border-left: 4px solid #4CAF50;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin-bottom: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 10px;
                text-align: left;
            }}
            th {{
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }}
            tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .overtime {{
                font-weight: bold;
                color: #d32f2f;
            }}
            .total-row {{
                background-color: #e8f5e9;
                font-weight: bold;
            }}
            .footer {{
                margin-top: 30px;
                padding: 15px;
                background-color: #f5f5f5;
                text-align: center;
                color: #666;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h2>ECC Overtime Report</h2>
            <p>{start_date.strftime("%B %d, %Y")} to {end_date.strftime("%B %d, %Y")}</p>
            {f'<p>Resident: {resident_name}</p>' if resident_name else '<p>All Residents</p>'}
        </div>
    """

    if not resident_data:
        html_content += """
        <div class="summary">
            <p>No overtime entries found for the selected date range.</p>
        </div>
        """
    else:
        # Calculate total overtime across all residents
        total_overtime_all = sum(data["total_overtime"] for data in resident_data.values())

        html_content += f"""
        <div class="summary">
            <h3>Summary</h3>
            <p><strong>Total Residents:</strong> {len(resident_data)}</p>
            <p><strong>Total Overtime Hours:</strong> <span class="overtime">{total_overtime_all:.2f}</span></p>
        </div>

        <h3>Detailed Breakdown</h3>
        """

        # Add table for each resident
        for resident_name, data in sorted(resident_data.items()):
            html_content += f"""
            <h4>{resident_name} - Total: <span class="overtime">{data['total_overtime']:.2f} hours</span></h4>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Role</th>
                        <th>Exit Time</th>
                        <th>Overtime Hours</th>
                    </tr>
                </thead>
                <tbody>
            """

            for entry in data["entries"]:
                html_content += f"""
                    <tr>
                        <td>{entry['date']}</td>
                        <td>{entry['role']}</td>
                        <td>{entry['exit_time'] if entry['exit_time'] else '-'}</td>
                        <td class="overtime">{entry['overtime']:.2f}</td>
                    </tr>
                """

            html_content += """
                </tbody>
            </table>
            """

    html_content += f"""
        <div class="footer">
            <p>This is an automated report from the ECC Sheet system.</p>
            <p>A CSV file with detailed data is attached to this email.</p>
        </div>
    </body>
    </html>
    """

    return html_content


def send_report_email(
    start_date: date,
    end_date: date,
    recipient_email: str = None,
    resident_id: int = None,
    resident_name: str = None,
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

        # Generate CSV content
        csv_content = generate_csv_report(start_date, end_date, resident_id)

        # Get resident data for HTML email
        query = TimeEntry.query.filter(
            TimeEntry.date >= start_date, TimeEntry.date <= end_date
        )
        if resident_id:
            query = query.filter(TimeEntry.resident_id == resident_id)

        entries = query.all()

        # Aggregate by resident
        resident_data = {}
        for entry in entries:
            res_name = entry.resident.name
            if res_name not in resident_data:
                resident_data[res_name] = {"entries": [], "total_overtime": 0.0}

            overtime = entry.calculate_overtime_hours()
            resident_data[res_name]["entries"].append(
                {
                    "date": entry.date.strftime("%Y-%m-%d"),
                    "role": entry.role.name,
                    "exit_time": entry.exit_time.strftime("%H:%M")
                    if entry.exit_time
                    else "",
                    "overtime": overtime,
                }
            )
            resident_data[res_name]["total_overtime"] += overtime

        # Build HTML content
        html_content = build_report_email_html(
            start_date, end_date, resident_data, resident_name
        )

        # Create message
        msg = MIMEMultipart("mixed")
        subject = f"ECC Overtime Report - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
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

        csv_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(csv_attachment)

        # Send email
        with smtplib.SMTP(Config.EMAIL_HOST, Config.EMAIL_PORT, timeout=30) as server:
            server.starttls()
            server.login(Config.EMAIL_USERNAME, Config.EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info("Report email sent successfully to %s", recipient)
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP Authentication failed: %s", e)
        return False

    except smtplib.SMTPException as e:
        logger.error("SMTP error sending report email: %s", e)
        return False

    except Exception as e:
        logger.error("Error sending report email: %s", e)
        return False
