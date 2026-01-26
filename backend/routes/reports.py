"""Report routes."""

import logging
from datetime import date, datetime

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..email_service import send_report_email
from ..models import TimeEntry
from ..report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_csv_content,
    get_resident_name,
)

bp = Blueprint("reports", __name__)
logger = logging.getLogger(__name__)


def _parse_report_params() -> tuple[date, date, str | None]:
    """Parse common report parameters from form data."""
    start_date = datetime.strptime(  # noqa: DTZ007
        request.form.get("start_date"), "%Y-%m-%d"
    ).date()
    end_date = datetime.strptime(  # noqa: DTZ007
        request.form.get("end_date"), "%Y-%m-%d"
    ).date()
    resident_id = request.form.get("resident_id") or None
    return start_date, end_date, resident_id


@bp.route("/reports")
def index():
    """View reports page."""
    return render_template("reports.html")


@bp.route("/api/report", methods=["POST"])
def generate():
    """Generate report for date range."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        query = build_entries_query(start_date, end_date, resident_id)
        resident_name = get_resident_name(resident_id)
        resident_data = aggregate_entries_by_resident(query.all())

        return render_template(
            "report_results.html",
            start_date=start_date,
            end_date=end_date,
            resident_data=resident_data,
            resident_name=resident_name,
            resident_id=resident_id,
        )

    except Exception as e:
        flash(f"Error generating report: {e!s}", "error")
        return redirect(url_for("reports.index"))


@bp.route("/api/report/export_csv", methods=["POST"])
def export_csv():
    """Export report to CSV."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        query = build_entries_query(start_date, end_date, resident_id)
        entries = query.order_by(TimeEntry.date, TimeEntry.resident_id).all()
        csv_content = generate_csv_content(entries)

        filename = f"overtime_report_{start_date}_{end_date}.csv"
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        flash(f"Error exporting report: {e!s}", "error")
        return redirect(url_for("reports.index"))


@bp.route("/api/report/send_email", methods=["POST"])
def send_email():
    """Send report via email."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        recipient_email = request.form.get("recipient_email")
        resident_name = get_resident_name(resident_id)

        # Send email
        success = send_report_email(
            start_date=start_date,
            end_date=end_date,
            recipient_email=recipient_email,
            resident_id=int(resident_id) if resident_id else None,
            resident_name=resident_name,
        )

        if success:
            recipient = recipient_email or "configured recipient"
            flash(f"Report emailed successfully to {recipient}", "success")
        else:
            flash("Failed to send email. Check email configuration and logs.", "error")

    except Exception as e:
        flash(f"Error sending email: {e!s}", "error")
        logger.error("Error in send_report_email_route: %s", e)

    return redirect(url_for("reports.index"))
