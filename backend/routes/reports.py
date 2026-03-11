"""Report routes."""

import logging
from datetime import date
from logging import Logger

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..audit import log_update
from ..auth import (
    admin_required,
    can_filter_reports_by_resident,
    can_view_all_reports,
    get_current_resident_id,
    is_payroll_admin,
    payroll_admin_required,
)
from ..errors import ValidationError
from ..models import PayrollSettings, TimeEntry, db
from ..report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_billing_csv_content,
    generate_csv_content,
    generate_payroll_xlsx,
    get_resident_name,
)

bp: Blueprint = Blueprint("reports", __name__)
logger: Logger = logging.getLogger(__name__)


def _reports_index_redirect():
    """Return the reports index redirect."""
    return redirect(url_for("reports.index"))


def _reports_flash_redirect(message: str, category: str = "error") -> Response:
    """Flash a message and redirect to the reports index."""
    flash(message, category)
    return _reports_index_redirect()


def _report_form_text(key: str) -> str:
    """Return a trimmed report form value."""
    return request.form.get(key, "").strip()


def _report_form_int(key: str) -> int | None:
    """Return an optional integer from the report form."""
    value = _report_form_text(key)
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError(f"'{key}' must be an integer.") from exc


def _apply_payroll_settings_form(settings: PayrollSettings) -> None:
    """Apply payroll-settings form values to the settings model."""
    settings.program = _report_form_text("program") or None
    settings.company = _report_form_text("company") or None
    settings.label_suffix = _report_form_text("label_suffix") or None
    settings.batch = _report_form_int("batch")
    settings.pay_code = _report_form_int("pay_code")
    settings.dept = _report_form_int("dept")
    settings.expense = _report_form_int("expense")
    settings.acct_unit = _report_form_int("acct_unit")


def _payroll_settings_details(settings: PayrollSettings) -> dict[str, str | int | None]:
    """Return the payroll settings fields tracked in audit logs."""
    return {
        "program": settings.program,
        "company": settings.company,
        "batch": settings.batch,
        "pay_code": settings.pay_code,
        "dept": settings.dept,
        "expense": settings.expense,
        "acct_unit": settings.acct_unit,
        "label_suffix": settings.label_suffix,
    }


def _report_entries(
    start_date: date,
    end_date: date,
    resident_id: int | None,
    *,
    ordered: bool = False,
) -> list[TimeEntry]:
    """Return report entries for a date range/filter."""
    query = build_entries_query(start_date, end_date, resident_id)
    if ordered:
        query = query.order_by(TimeEntry.date, TimeEntry.resident_id)
    return query.all()


def _file_response(content: str | bytes, mimetype: str, filename: str) -> Response:
    """Return a download response for generated report content."""
    escaped_filename = filename.replace("\\", "\\\\").replace('"', '\\"')
    return Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{escaped_filename}"'},
    )


def _require_extended_report_permission(message: str) -> Response | None:
    """Return an error redirect when extended report access is unavailable."""
    if can_view_all_reports():
        return None
    return _reports_flash_redirect(message)


def _detailed_csv_content(
    start_date: date, end_date: date, resident_id: int | None
) -> str:
    """Build detailed report CSV content."""
    return generate_csv_content(
        _report_entries(start_date, end_date, resident_id, ordered=True)
    )


def _billing_csv_content(
    start_date: date, end_date: date, resident_id: int | None
) -> str:
    """Build billing report CSV content."""
    return generate_billing_csv_content(
        aggregate_entries_by_resident(
            _report_entries(start_date, end_date, resident_id)
        )
    )


def _payroll_xlsx_content(
    start_date: date, end_date: date, resident_id: int | None
) -> bytes:
    """Build payroll XLSX content."""
    return generate_payroll_xlsx(
        aggregate_entries_by_resident(
            _report_entries(start_date, end_date, resident_id)
        ),
        start_date,
        end_date,
        PayrollSettings.get_or_create(),
    )


def _run_file_report_action(
    *,
    filename: str,
    mimetype: str,
    content_builder,
    log_message: str,
    error_message: str,
):
    """Run a report action that returns a downloadable file."""

    def _export(start_date: date, end_date: date, resident_id: int | None):
        return _file_response(
            content_builder(start_date, end_date, resident_id),
            mimetype=mimetype,
            filename=filename.format(start_date=start_date, end_date=end_date),
        )

    return _run_report_action(
        _export,
        log_message=log_message,
        error_message=error_message,
    )


def _run_report_action(action, *, log_message: str, error_message: str):
    """Run a report action with shared validation and error handling."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        return action(start_date, end_date, resident_id)
    except ValidationError as exc:
        return _reports_flash_redirect(str(exc))
    except Exception:
        logger.exception(log_message)
        return _reports_flash_redirect(error_message)


def _parse_report_params() -> tuple[date, date, int | None]:
    """Parse common report parameters from form data."""
    start_date_raw = request.form.get("start_date")
    end_date_raw = request.form.get("end_date")
    if not start_date_raw or not end_date_raw:
        raise ValidationError("Start date and end date are required")

    try:
        start_date = date.fromisoformat(start_date_raw)
    except ValueError as exc:
        raise ValidationError(f"Invalid start_date: {start_date_raw}") from exc

    try:
        end_date = date.fromisoformat(end_date_raw)
    except ValueError as exc:
        raise ValidationError(f"Invalid end_date: {end_date_raw}") from exc

    if not can_filter_reports_by_resident():
        # -1 is intentional: it is truthy (so build_entries_query applies the
        # filter) but never matches a real resident_id, returning empty results
        # for a user whose name has no corresponding Resident record.
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
        can_filter_reports=can_filter_reports_by_resident(),
        can_use_extended_reports=can_view_all_reports(),
        current_resident_id=get_current_resident_id(),
    )


@bp.route("/api/report", methods=["POST"])
def generate():
    """Generate report for date range."""

    def _render_report(start_date: date, end_date: date, resident_id: int | None):
        return render_template(
            "report_results.html",
            start_date=start_date,
            end_date=end_date,
            resident_data=aggregate_entries_by_resident(
                _report_entries(start_date, end_date, resident_id)
            ),
            resident_name=get_resident_name(resident_id),
            resident_id=resident_id,
            can_use_extended_reports=can_view_all_reports(),
        )

    return _run_report_action(
        _render_report,
        log_message="Error generating report",
        error_message="Error generating report. Check logs for details.",
    )


@bp.route("/api/report/export_csv", methods=["POST"])
def export_csv():
    """Export detailed report to CSV."""
    return _run_file_report_action(
        filename="overtime_report_detailed_{start_date}_{end_date}.csv",
        mimetype="text/csv",
        content_builder=_detailed_csv_content,
        log_message="Error exporting report",
        error_message="Error exporting report. Check logs for details.",
    )


@bp.route("/api/report/export_billing_csv", methods=["POST"])
def export_billing_csv():
    """Export billing/payroll summary to CSV."""
    if resp := _require_extended_report_permission(
        "You do not have permission to export the billing report."
    ):
        return resp

    return _run_file_report_action(
        filename="overtime_billing_{start_date}_{end_date}.csv",
        mimetype="text/csv",
        content_builder=_billing_csv_content,
        log_message="Error exporting billing report",
        error_message="Error exporting billing report. Check logs for details.",
    )


@bp.route("/api/report/export_payroll_xlsx", methods=["POST"])
def export_payroll_xlsx():
    """Export payroll data as Lawson/UPHS formatted .xlsx file."""
    if resp := _require_extended_report_permission(
        "You do not have permission to export the payroll report."
    ):
        return resp

    return _run_file_report_action(
        filename="payroll_{start_date}_{end_date}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_builder=_payroll_xlsx_content,
        log_message="Error exporting payroll report",
        error_message="Error exporting payroll report. Check logs for details.",
    )


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

    try:
        _apply_payroll_settings_form(settings)
        log_update(
            "PayrollSettings",
            settings.id,
            details=_payroll_settings_details(settings),
        )
        db.session.commit()
        flash("Payroll settings saved successfully.", "success")
    except ValidationError as exc:
        db.session.rollback()
        logger.debug("Invalid payroll settings input", exc_info=True)
        flash(str(exc), "error")
    except Exception:
        db.session.rollback()
        logger.exception("Error saving payroll settings")
        flash("Error saving settings.", "error")

    return redirect(url_for("reports.payroll_settings"))
