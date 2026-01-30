"""Entry routes for time entry management."""

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, request, url_for

from ..audit import log_create, log_delete, log_update
from ..models import DailySheet, TimeEntry, db
from ..utils import handle_db_error

bp = Blueprint("entries", __name__, url_prefix="/entries")


@bp.route("/add", methods=["POST"])
@handle_db_error
def add():
    """Add a new time entry."""
    sheet_date_str = ""
    try:
        sheet_date_str = request.form.get("date")
        sheet_date = datetime.strptime(sheet_date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if daily_sheet and daily_sheet.locked:
            flash("Cannot add entry - sheet is locked", "error")
            return redirect(url_for("sheets.view", date_str=sheet_date_str))

        resident_id = request.form.get("resident_id")
        role_id = request.form.get("role_id")
        exit_time_str = request.form.get("exit_time")
        start_time_str = request.form.get("start_time")

        # Validate required fields
        if not resident_id:
            flash("Resident is required", "error")
            return redirect(url_for("sheets.view", date_str=sheet_date_str))

        # Parse exit time
        exit_time = None
        if exit_time_str:
            exit_time = datetime.strptime(exit_time_str, "%H:%M").time()  # noqa: DTZ007

        # Parse start time (for backup roles)
        start_time = None
        if start_time_str:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()  # noqa: DTZ007

        entry = TimeEntry(
            date=sheet_date,
            resident_id=resident_id,
            role_id=role_id,
            exit_time=exit_time,
            start_time=start_time,
        )

        db.session.add(entry)
        db.session.commit()

        # Log the action
        log_create(
            "TimeEntry",
            entry.id,
            {
                "date": sheet_date_str,
                "resident": entry.resident.name,
                "role": entry.role.name,
            },
        )

        flash("Entry added successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding entry: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=sheet_date_str))


@bp.route("/<int:entry_id>/update", methods=["POST"])
@handle_db_error
def update(entry_id):
    """Update an existing time entry."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        abort(404)

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=entry.date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot update entry - sheet is locked", "error")
        date_str = entry.date.strftime("%Y-%m-%d")
        return redirect(url_for("sheets.view", date_str=date_str))

    try:
        changes = {}

        exit_time_str = request.form.get("exit_time")
        if exit_time_str:
            entry.exit_time = datetime.strptime(exit_time_str, "%H:%M").time()  # noqa: DTZ007
            changes["exit_time"] = exit_time_str
        else:
            entry.exit_time = None
            changes["exit_time"] = "cleared"

        # Handle start_time for backup roles
        start_time_str = request.form.get("start_time")
        if start_time_str is not None:  # Only update if field was submitted
            if start_time_str:
                entry.start_time = datetime.strptime(start_time_str, "%H:%M").time()  # noqa: DTZ007
                changes["start_time"] = start_time_str
            else:
                entry.start_time = None
                changes["start_time"] = "cleared"

        db.session.commit()

        # Log the action
        log_update("TimeEntry", entry.id, changes)

        flash("Entry updated successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating entry: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=entry.date.strftime("%Y-%m-%d")))


@bp.route("/<int:entry_id>/delete", methods=["POST"])
@handle_db_error
def delete(entry_id):
    """Delete a time entry."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        abort(404)
    sheet_date = entry.date

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot delete entry - sheet is locked", "error")
        date_str = sheet_date.strftime("%Y-%m-%d")
        redirect_url = url_for("sheets.view", date_str=date_str)
        return redirect(redirect_url)

    try:
        # Log before deleting
        log_delete(
            "TimeEntry",
            entry.id,
            {
                "date": str(entry.date),
                "resident": entry.resident.name,
                "role": entry.role.name,
            },
        )

        db.session.delete(entry)
        db.session.commit()
        flash("Entry deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting entry: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=sheet_date.strftime("%Y-%m-%d")))
