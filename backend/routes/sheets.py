"""Sheet routes for daily sheet management."""

from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from sqlalchemy.orm import joinedload

from ..audit import log_lock
from ..auth import is_admin, is_first_call
from ..holidays import is_weekend_or_holiday
from ..models import DailySheet, Role, TimeEntry, db
from ..utils import get_effective_date, get_philadelphia_time, handle_db_error

bp: Blueprint = Blueprint(
    "sheets",
    __name__,
)


def _get_sheet_context(sheet_date):
    """Return call_team_entries, overtime_entries, and overtime_roles for a date."""
    all_entries = (
        TimeEntry.query.filter_by(date=sheet_date)
        .options(joinedload(TimeEntry.role), joinedload(TimeEntry.resident))
        .order_by(TimeEntry.id)
        .all()
    )
    call_team_entries = sorted(
        [e for e in all_entries if e.role and e.role.is_call_team],
        key=lambda e: e.role.display_order if e.role.display_order is not None else 0,
    )
    overtime_entries = [e for e in all_entries if not (e.role and e.role.is_call_team)]
    overtime_roles = (
        Role.query.filter(Role.is_call_team.isnot(True))
        .order_by(Role.display_order)
        .all()
    )
    return call_team_entries, overtime_entries, overtime_roles


def _render_sheet(daily_sheet: DailySheet | None, sheet_date: date) -> str:
    if not daily_sheet:
        daily_sheet = DailySheet(date=sheet_date)
        db.session.add(daily_sheet)
        db.session.commit()

    call_team_entries, overtime_entries, overtime_roles = _get_sheet_context(sheet_date)

    # Calculate previous and next dates
    prev_date = sheet_date - timedelta(days=1)
    next_date = sheet_date + timedelta(days=1)

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        overtime_entries=overtime_entries,
        call_team_entries=call_team_entries,
        overtime_roles=overtime_roles,
        today=sheet_date,
        prev_date=prev_date,
        next_date=next_date,
        current_time=get_philadelphia_time(),
        is_weekend_or_holiday=is_weekend_or_holiday(sheet_date),
        can_edit=is_admin() or is_first_call(sheet_date),
    )


@bp.route("/")
def index():
    """Dashboard showing today's sheet."""
    today = get_effective_date()
    daily_sheet: DailySheet | None = DailySheet.query.filter_by(date=today).first()

    return _render_sheet(daily_sheet, today)


@bp.route("/sheets/<date_str>")
def view(date_str):
    """View sheet for a specific date."""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        flash("Invalid date format", "error")
        return redirect(url_for("sheets.index"))

    daily_sheet: DailySheet | None = DailySheet.query.filter_by(date=sheet_date).first()
    return _render_sheet(daily_sheet, sheet_date)


@bp.route("/sheets/<date_str>/lock", methods=["POST"])
@handle_db_error
def lock(date_str):
    """Lock/unlock a daily sheet."""
    try:
        sheet_date: date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        if not (is_admin() or is_first_call(sheet_date)):
            flash(
                "Only the first call resident or an admin can lock/unlock the sheet.",
                "error",
            )
            return redirect(url_for("sheets.view", date_str=date_str))
        daily_sheet: DailySheet | None = DailySheet.query.filter_by(
            date=sheet_date
        ).first()

        if not daily_sheet:
            daily_sheet = DailySheet(date=sheet_date)
            db.session.add(daily_sheet)

        daily_sheet.locked = not daily_sheet.locked

        # Track who and when
        if daily_sheet.locked:
            daily_sheet.locked_by = current_app.config["USER_NAME"]
            daily_sheet.locked_at = datetime.now()  # noqa: DTZ005
        else:
            daily_sheet.locked_by = None
            daily_sheet.locked_at = None

        db.session.commit()

        # Log lock/unlock action
        log_lock(date_str, locked=daily_sheet.locked)

        status = "locked" if daily_sheet.locked else "unlocked"
        flash(f"Sheet {status} successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error locking sheet: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=date_str))
