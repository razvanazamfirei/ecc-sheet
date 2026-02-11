"""Sheet routes for daily sheet management."""

from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, url_for

from ..audit import log_lock
from ..holidays import is_weekend_or_holiday
from ..models import DailySheet, Role, TimeEntry, db
from ..utils import get_effective_date, get_philadelphia_time, handle_db_error

bp = Blueprint(
    "sheets",
    __name__,
)


@bp.route("/")
def index():
    """Dashboard showing today's sheet."""
    today = get_effective_date()
    daily_sheet = DailySheet.query.filter_by(date=today).first()

    if not daily_sheet:
        daily_sheet = DailySheet(date=today)
        db.session.add(daily_sheet)
        db.session.commit()

    # Get all time entries for today
    time_entries = TimeEntry.query.filter_by(date=today).order_by(TimeEntry.id).all()

    # Get all roles ordered
    roles = Role.query.order_by(Role.display_order).all()

    # Calculate previous and next dates
    prev_date = today - timedelta(days=1)
    next_date = today + timedelta(days=1)

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        time_entries=time_entries,
        roles=roles,
        today=today,
        prev_date=prev_date,
        next_date=next_date,
        current_time=get_philadelphia_time(),
        is_weekend_or_holiday=is_weekend_or_holiday(today),
    )


@bp.route("/sheets/<date_str>")
def view(date_str):
    """View sheet for a specific date."""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        flash("Invalid date format", "error")
        return redirect(url_for("sheets.index"))

    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()

    if not daily_sheet:
        daily_sheet = DailySheet(date=sheet_date)
        db.session.add(daily_sheet)
        db.session.commit()

    time_entries = (
        TimeEntry.query.filter_by(date=sheet_date).order_by(TimeEntry.id).all()
    )
    roles = Role.query.order_by(Role.display_order).all()

    # Calculate previous and next dates
    prev_date = sheet_date - timedelta(days=1)
    next_date = sheet_date + timedelta(days=1)

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        time_entries=time_entries,
        roles=roles,
        today=sheet_date,
        prev_date=prev_date,
        next_date=next_date,
        current_time=get_philadelphia_time(),
        is_weekend_or_holiday=is_weekend_or_holiday(sheet_date),
    )


@bp.route("/sheets/<date_str>/lock", methods=["POST"])
@handle_db_error
def lock(date_str):
    """Lock/unlock a daily sheet."""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()

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
        log_lock(date_str, daily_sheet.locked)

        status = "locked" if daily_sheet.locked else "unlocked"
        flash(f"Sheet {status} successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error locking sheet: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=date_str))
