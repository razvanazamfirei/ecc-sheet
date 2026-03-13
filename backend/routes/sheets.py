"""Sheet routes for daily sheet management."""

import logging
from datetime import date, timedelta

from flask import Blueprint, flash, render_template
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..audit import log_lock
from ..auth import get_current_user, is_admin, is_first_call
from ..holidays import is_weekend_or_holiday
from ..models import DailySheet, Role, TimeEntry, db
from ..utils import get_effective_date, get_philadelphia_time
from ._helpers import parse_iso_date, redirect_to, sheet_view_redirect

bp: Blueprint = Blueprint(
    "sheets",
    __name__,
)
logger = logging.getLogger(__name__)


def _parse_sheet_date(date_str: str) -> date | None:
    """Parse a sheet date or flash an error when invalid."""
    try:
        return parse_iso_date(date_str)
    except ValueError:
        flash("Invalid date format", "error")
        return None


def _lock_error_response(date_str: str):
    """Rollback a failed lock mutation and redirect back to the sheet."""
    db.session.rollback()
    flash("An unexpected error occurred. Please try again.", "error")
    return sheet_view_redirect(date_str)


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
        flash(
            "Only the first call resident or an admin can lock/unlock the sheet.",
            "error",
        )
        return sheet_view_redirect(date_str)

    try:
        daily_sheet = _get_or_create_daily_sheet(sheet_date, commit=False)

        daily_sheet.locked = not daily_sheet.locked

        # Track who and when
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

        db.session.commit()
    except Exception:
        logger.exception("Failed to toggle sheet lock for %s", date_str)
        return _lock_error_response(date_str)

    status = "locked" if daily_sheet.locked else "unlocked"
    flash(f"Sheet {status} successfully", "success")

    return sheet_view_redirect(date_str)
