"""Report routes."""

import logging
from collections.abc import Callable
from datetime import date
from logging import Logger

from flask import Blueprint, render_template, request
from werkzeug.wrappers import Response

from backend.audit import log_update
from backend.auth import (
    admin_required,
    can_filter_reports_by_resident,
    can_view_all_reports,
    get_current_resident_id,
    is_payroll_admin,
    payroll_admin_required,
)
from backend.errors import ValidationError
from backend.models import PayrollSettings, TimeEntry
from backend.report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_csv_content,
    generate_payroll_xlsx,
    get_resident_name,
)
from backend.routes._forms import form_text, optional_form_int
from backend.routes._helpers import (
    commit_flash_redirect,
    diff_snapshots,
    flash_redirect,
    parse_iso_date,
    rollback_flash_redirect,
)
from backend.type_defs import ResidentData

bp: Blueprint = Blueprint("reports", __name__)
logger: Logger = logging.getLogger(__name__)


def _report_form_int(key: str) -> int | None:
    """Return an optional integer from the report form."""
    try:
        return optional_form_int(key)
    except ValueError as exc:
        raise ValidationError(f"'{key}' must be an integer.") from exc


def _apply_payroll_settings_form(settings: PayrollSettings) -> None:
    """Apply payroll-settings form values to the settings model."""
    settings.program = form_text("program") or None
    settings.company = form_text("company") or None
    settings.label_suffix = form_text("label_suffix") or None
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


def _exclude_zero_overtime_flag() -> bool:
    """Return True when the form requests zero-overtime residents be excluded."""
    return request.form.get("exclude_zero_overtime", "0") == "1"


def _filter_zero_overtime(resident_data: ResidentData) -> ResidentData:
    """Remove residents with zero total overtime from the aggregated data."""
    return {k: v for k, v in resident_data.items() if v["total_overtime"] > 0}


def _detailed_csv_content(
    start_date: date, end_date: date, resident_id: int | None
) -> str:
    """Build detailed report CSV content."""
    entries = _report_entries(start_date, end_date, resident_id, ordered=True)
    if _exclude_zero_overtime_flag():
        aggregated = aggregate_entries_by_resident(entries)
        zero_res_ids = {k for k, v in aggregated.items() if v["total_overtime"] == 0}
        entries = [e for e in entries if e.resident_id not in zero_res_ids]
    return generate_csv_content(entries)


def _payroll_xlsx_content(
    start_date: date, end_date: date, resident_id: int | None
) -> bytes:
    """Build payroll XLSX content."""
    aggregated = aggregate_entries_by_resident(
        _report_entries(start_date, end_date, resident_id)
    )
    if _exclude_zero_overtime_flag():
        aggregated = _filter_zero_overtime(aggregated)
    return generate_payroll_xlsx(
        aggregated,
        start_date,
        end_date,
        PayrollSettings.get_or_create(),
    )


def _run_file_report_action(
    *,
    filename: str,
    mimetype: str,
    content_builder: Callable[[date, date, int | None], bytes | str],
    log_message: str,
    error_message: str,
) -> Response:
    """Run a report action that returns a downloadable file."""

    def _export(start_date: date, end_date: date, resident_id: int | None) -> Response:
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


def _run_report_action(
    action: Callable[[date, date, int | None], Response],
    *,
    log_message: str,
    error_message: str,
) -> Response:
    """Run a report action with shared validation and error handling."""
    try:
        start_date, end_date, resident_id = _parse_report_params()
        return action(start_date, end_date, resident_id)
    except ValidationError as exc:
        return flash_redirect("reports.index", str(exc))
    except Exception:
        logger.exception(log_message)
        return flash_redirect("reports.index", error_message)


def _parse_report_params() -> tuple[date, date, int | None]:
    """Parse common report parameters from form data."""
    start_date_raw = form_text("start_date")
    end_date_raw = form_text("end_date")
    if not start_date_raw or not end_date_raw:
        raise ValidationError("Start date and end date are required")

    try:
        start_date = parse_iso_date(
            start_date_raw,
            error_message=f"Invalid start_date: {start_date_raw}",
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    try:
        end_date = parse_iso_date(
            end_date_raw,
            error_message=f"Invalid end_date: {end_date_raw}",
        )
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    if not can_filter_reports_by_resident():
        # -1 is intentional: it is truthy (so build_entries_query applies the
        # filter) but never matches a real resident_id, returning empty results
        # for a user whose name has no corresponding Resident record.
        resident_id = get_current_resident_id() or -1
    else:
        raw = form_text("resident_id")
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
    suffix = "_excl_zero" if _exclude_zero_overtime_flag() else ""
    return _run_file_report_action(
        filename=f"overtime_report_detailed_{{start_date}}_{{end_date}}{suffix}.csv",
        mimetype="text/csv",
        content_builder=_detailed_csv_content,
        log_message="Error exporting report",
        error_message="Error exporting report. Check logs for details.",
    )


@bp.route("/api/report/export_payroll_xlsx", methods=["POST"])
def export_payroll_xlsx():
    """Export payroll data as Lawson/UPHS formatted .xlsx file."""
    if not can_view_all_reports():
        return flash_redirect(
            "reports.index",
            "You do not have permission to export the payroll report.",
        )

    suffix = "_excl_zero" if _exclude_zero_overtime_flag() else ""
    return _run_file_report_action(
        filename=f"payroll_{{start_date}}_{{end_date}}{suffix}.xlsx",
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
    before = _payroll_settings_details(settings)

    try:
        _apply_payroll_settings_form(settings)
    except ValidationError as exc:
        logger.debug("Invalid payroll settings input", exc_info=True)
        return rollback_flash_redirect("reports.payroll_settings", str(exc), "error")

    after = _payroll_settings_details(settings)

    def _save() -> None:
        log_update(
            "PayrollSettings",
            settings.id,
            changes=diff_snapshots(before, after),
            details=after,
        )

    return commit_flash_redirect(
        _save,
        endpoint="reports.payroll_settings",
        logger=logger,
        errors=("Error saving payroll settings", "Error saving settings."),
        success_message="Payroll settings saved successfully.",
    )
