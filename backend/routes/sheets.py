"""Sheet routes for daily sheet management."""

import logging
from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from backend.audit import log_lock
from backend.auth import get_current_user, is_admin, is_first_call
from backend.db_session import commit_or_rollback
from backend.holidays import is_weekend_or_holiday
from backend.models import DailySheet, Role, TimeEntry, db
from backend.routes._helpers import (
    commit_flash_redirect,
    flash_sheet_redirect,
    parse_iso_date_or_none,
    redirect_to,
    rollback_flash_redirect,
)
from backend.utils import (
    _wants_json_response,
    get_effective_date,
    get_philadelphia_time,
)

bp: Blueprint = Blueprint(
    "sheets",
    __name__,
)
logger = logging.getLogger(__name__)


def _parse_sheet_date(date_str: str) -> date | None:
    """Parse a sheet date or flash an error when invalid."""
    return parse_iso_date_or_none(date_str)


def _get_or_create_daily_sheet(sheet_date: date, *, commit: bool = True) -> DailySheet:
    """Return the sheet for a date, handling concurrent inserts safely."""
    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet is not None:
        return daily_sheet

    daily_sheet = DailySheet(date=sheet_date)
    db.session.add(daily_sheet)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        existing_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if existing_sheet is None:
            raise
        return existing_sheet

    if commit:
        db.session.commit()

    return daily_sheet


def _get_sheet_context(sheet_date):
    """Return call_team_entries, overtime_entries, and overtime_roles for a date."""
    all_entries = (
        TimeEntry.query.filter_by(date=sheet_date)
        .options(joinedload(TimeEntry.role), joinedload(TimeEntry.resident))
        .all()
    )

    def _entry_sort_key(entry: TimeEntry) -> tuple[int, str, int]:
        role_order = (
            entry.role.display_order
            if entry.role and entry.role.display_order is not None
            else 9999
        )
        resident_name = entry.resident.name.casefold() if entry.resident else ""
        return role_order, resident_name, entry.id

    call_team_entries = sorted(
        [e for e in all_entries if e.role and e.role.is_call_team],
        key=_entry_sort_key,
    )
    overtime_entries = sorted(
        [e for e in all_entries if not (e.role and e.role.is_call_team)],
        key=_entry_sort_key,
    )
    overtime_roles = (
        Role.query.filter(Role.is_call_team.isnot(True))
        .order_by(Role.display_order)
        .all()
    )
    return call_team_entries, overtime_entries, overtime_roles


def _render_sheet(daily_sheet: DailySheet, sheet_date: date) -> str:
    call_team_entries, overtime_entries, overtime_roles = _get_sheet_context(sheet_date)

    # Calculate previous and next dates
    prev_date = sheet_date - timedelta(days=1)
    next_date = sheet_date + timedelta(days=1)
    current_time = get_philadelphia_time()
    auto_lock_target_date = (
        (current_time - timedelta(days=1)).date() if current_time.hour == 8 else None
    )
    show_auto_lock_warning = (
        not daily_sheet.locked
        and auto_lock_target_date is not None
        and sheet_date == auto_lock_target_date
    )
    minutes_until_lock = 60 - current_time.minute if show_auto_lock_warning else None

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        overtime_entries=overtime_entries,
        call_team_entries=call_team_entries,
        overtime_roles=overtime_roles,
        today=sheet_date,
        prev_date=prev_date,
        next_date=next_date,
        current_time=current_time,
        show_auto_lock_warning=show_auto_lock_warning,
        minutes_until_lock=minutes_until_lock,
        is_weekend_or_holiday=is_weekend_or_holiday(sheet_date),
        can_edit=is_admin() or is_first_call(sheet_date),
    )


@bp.route("/")
def index():
    """Dashboard showing today's sheet."""
    today = get_effective_date()
    daily_sheet = _get_or_create_daily_sheet(today)
    return _render_sheet(daily_sheet, today)


@bp.route("/sheets/<date_str>")
def view(date_str):
    """View sheet for a specific date."""
    sheet_date = _parse_sheet_date(date_str)
    if sheet_date is None:
        return redirect_to("sheets.index")

    daily_sheet = _get_or_create_daily_sheet(sheet_date)
    return _render_sheet(daily_sheet, sheet_date)


@bp.route("/sheets/<date_str>/lock", methods=["POST"])
def lock(date_str):
    """Lock/unlock a daily sheet."""
    sheet_date = _parse_sheet_date(date_str)
    if sheet_date is None:
        return redirect_to("sheets.index")

    if not (is_admin() or is_first_call(sheet_date)):
        return flash_sheet_redirect(
            date_str,
            "Only the first call resident or an admin can lock/unlock the sheet.",
            "error",
        )

    try:
        daily_sheet = _get_or_create_daily_sheet(sheet_date, commit=False)
    except Exception:
        logger.exception("Failed to toggle sheet lock for %s", date_str)
        return rollback_flash_redirect(
            "sheets.view",
            "An unexpected error occurred. Please try again.",
            date_str=date_str,
        )

    def _toggle_lock() -> str:
        daily_sheet.locked = not daily_sheet.locked

        if daily_sheet.locked:
            daily_sheet.locked_by = get_current_user()
            daily_sheet.locked_at = get_philadelphia_time()
        else:
            daily_sheet.locked_by = None
            daily_sheet.locked_at = None

        try:
            log_lock(date_str, locked=daily_sheet.locked)
        except Exception:
            logger.warning("Audit log failed for sheet %s", date_str, exc_info=True)

        return f"Sheet {'locked' if daily_sheet.locked else 'unlocked'} successfully"

    if _wants_json_response():
        try:
            message = commit_or_rollback(_toggle_lock)
        except Exception:
            logger.exception("Failed to toggle sheet lock for %s", date_str)
            db.session.rollback()
            error_msg = "An unexpected error occurred. Please try again."
            return jsonify({"success": False, "message": error_msg}), 500

        locked_at_str = (
            daily_sheet.locked_at.strftime("%m/%d %H:%M")
            if daily_sheet.locked_at
            else None
        )
        return jsonify(
            {
                "success": True,
                "locked": daily_sheet.locked,
                "locked_by": daily_sheet.locked_by,
                "locked_at": locked_at_str,
                "show_import_button": not daily_sheet.locked,
                "message": message,
            }
        )

    return commit_flash_redirect(
        _toggle_lock,
        endpoint="sheets.view",
        logger=logger,
        errors=(
            f"Failed to toggle sheet lock for {date_str}",
            "An unexpected error occurred. Please try again.",
        ),
        success_message=lambda message: message,
        date_str=date_str,
    )
