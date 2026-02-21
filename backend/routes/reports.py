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

from ..auth import (
    admin_required,
    can_view_all_reports,
    get_current_resident_id,
    is_admin,
    is_payroll_admin,
    payroll_admin_required,
)
from ..email_service import send_report_email
from ..models import PayrollSettings, TimeEntry, db
from ..report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_billing_csv_content,
    generate_csv_content,
    generate_payroll_xlsx,
    get_resident_name,
)

bp = Blueprint("reports", __name__)
logger = logging.getLogger(__name__)


def _parse_report_params() -> tuple[date, date, str | int | None]:
    """Parse common report parameters from form data.

    If the current user cannot view all reports, the resident_id is forced
    to their own resident record regardless of what was submitted.
    """
    start_date = datetime.strptime(  # noqa: DTZ007
        request.form.get("start_date"), "%Y-%m-%d"
    ).date()
    end_date = datetime.strptime(  # noqa: DTZ007
        request.form.get("end_date"), "%Y-%m-%d"
    ).date()

    if not can_view_all_reports():
        resident_id = get_current_resident_id() or -1
    else:
        raw = request.form.get("resident_id", "").strip()
        resident_id = int(raw) if raw else None

    return start_date, end_date, resident_id


@bp.route("/reports")
def index():
    """View reports page."""
    return render_template(
        "reports.html",
        can_view_all=can_view_all_reports(),
        current_resident_id=get_current_resident_id(),
    )


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
            can_view_all=can_view_all_reports(),
        )

    except Exception as e:
        logger.exception("Error generating report: %s", e)
        flash("Error generating report. Check logs for details.", "error")
        return redirect(url_for("reports.index"))


@bp.route("/api/report/export_csv", methods=["POST"])
def export_csv():
    """Export detailed report to CSV."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        query = build_entries_query(start_date, end_date, resident_id)
        entries = query.order_by(TimeEntry.date, TimeEntry.resident_id).all()
        csv_content = generate_csv_content(entries)

        filename = f"overtime_report_detailed_{start_date}_{end_date}.csv"
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.exception("Error exporting report: %s", e)
        flash("Error exporting report. Check logs for details.", "error")
        return redirect(url_for("reports.index"))


@bp.route("/api/report/export_billing_csv", methods=["POST"])
def export_billing_csv():
    """Export billing/payroll summary to CSV."""
    if not can_view_all_reports():
        flash("You do not have permission to export the billing report.", "error")
        return redirect(url_for("reports.index"))
    try:
        start_date, end_date, resident_id = _parse_report_params()
        query = build_entries_query(start_date, end_date, resident_id)
        entries = query.all()
        resident_data = aggregate_entries_by_resident(entries)
        csv_content = generate_billing_csv_content(resident_data)

        filename = f"overtime_billing_{start_date}_{end_date}.csv"
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.exception("Error exporting billing report: %s", e)
        flash("Error exporting billing report. Check logs for details.", "error")
        return redirect(url_for("reports.index"))


@bp.route("/api/report/send_email", methods=["POST"])
def send_email():
    """Send report via email."""
    if not is_admin():
        flash("Admin privileges required to send email reports.", "error")
        return redirect(url_for("reports.index"))
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


@bp.route("/api/report/export_payroll_xlsx", methods=["POST"])
def export_payroll_xlsx():
    """Export payroll data as Lawson/UPHS formatted .xlsx file."""
    if not can_view_all_reports():
        flash("You do not have permission to export the payroll report.", "error")
        return redirect(url_for("reports.index"))
    try:
        start_date, end_date, resident_id = _parse_report_params()
        query = build_entries_query(start_date, end_date, resident_id)
        entries = query.all()
        resident_data = aggregate_entries_by_resident(entries)
        settings = PayrollSettings.get_or_create()
        xlsx_bytes = generate_payroll_xlsx(
            resident_data, start_date, end_date, settings
        )

        filename = f"payroll_{start_date}_{end_date}.xlsx"
        return Response(
            xlsx_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.exception("Error exporting payroll report: %s", e)
        flash("Error exporting payroll report. Check logs for details.", "error")
        return redirect(url_for("reports.index"))


@bp.route("/payroll-settings", methods=["GET"])
@admin_required
def payroll_settings():
    """View payroll export settings. Editable only for payroll admins."""
    settings = PayrollSettings.get_or_create()
    return render_template(
        "payroll_settings.html", settings=settings, can_edit=is_payroll_admin()
    )


@bp.route("/payroll-settings", methods=["POST"])
@admin_required
@payroll_admin_required
def payroll_settings_save():
    """Save payroll export settings."""

    settings = PayrollSettings.get_or_create()
    settings.program = request.form.get("program", "").strip() or None
    settings.company = request.form.get("company", "").strip() or None
    settings.label_suffix = request.form.get("label_suffix", "").strip() or None

    def _int_or_none(key):
        val = request.form.get(key, "").strip()
        return int(val) if val.isdigit() else None

    settings.batch = _int_or_none("batch")
    settings.pay_code = _int_or_none("pay_code")
    settings.dept = _int_or_none("dept")
    settings.expense = _int_or_none("expense")
    settings.acct_unit = _int_or_none("acct_unit")

    try:
        db.session.commit()
        flash("Payroll settings saved successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving settings: {e!s}", "error")

    return redirect(url_for("reports.payroll_settings"))
