"""Entry routes for time entry management."""

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, request, url_for

from ..audit import log_create, log_delete, log_update
from ..auth import is_admin, is_first_call
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
        if not sheet_date_str:
            flash("Date is required", "error")
            return redirect(url_for("sheets.index"))
        sheet_date = datetime.strptime(sheet_date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        if not (is_admin() or is_first_call(sheet_date)):
            flash("Only the first call resident or an admin can add entries.", "error")
            return redirect(url_for("sheets.view", date_str=sheet_date_str))

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if daily_sheet and daily_sheet.locked:
            flash("Cannot add entry - sheet is locked", "error")
            return redirect(url_for("sheets.view", date_str=sheet_date_str))

        resident_id_raw = request.form.get("resident_id")
        role_id_raw = request.form.get("role_id")
        exit_time_str = request.form.get("exit_time")
        start_time_str = request.form.get("start_time")

        # Validate required fields
        if not resident_id_raw or not role_id_raw:
            flash("Resident and role are required", "error")
            return redirect(url_for("sheets.view", date_str=sheet_date_str))
        try:
            resident_id = int(resident_id_raw)
            role_id = int(role_id_raw)
        except ValueError:
            flash("Resident and role must be valid IDs", "error")
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
        resident_name = (
            entry.resident.name if entry.resident else str(entry.resident_id)
        )
        role_name = entry.role.name if entry.role else str(entry.role_id)
        log_create(
            "TimeEntry",
            entry.id,
            {
                "date": sheet_date_str,
                "resident": resident_name,
                "role": role_name,
                "exit_time": exit_time_str or None,
                "start_time": start_time_str or None,
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

    if not (is_admin() or is_first_call(entry.date)):
        flash("Only the first call resident or an admin can update entries.", "error")
        return redirect(
            url_for("sheets.view", date_str=entry.date.strftime("%Y-%m-%d"))
        )

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=entry.date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot update entry - sheet is locked", "error")
        date_str = entry.date.strftime("%Y-%m-%d")
        return redirect(url_for("sheets.view", date_str=date_str))

    try:
        changes = {}

        # Store old values for audit
        old_exit_time = entry.exit_time.strftime("%H:%M") if entry.exit_time else None
        old_start_time = (
            entry.start_time.strftime("%H:%M") if entry.start_time else None
        )

        exit_time_str = request.form.get("exit_time")
        if exit_time_str:
            entry.exit_time = datetime.strptime(exit_time_str, "%H:%M").time()  # noqa: DTZ007
            if old_exit_time != exit_time_str:
                changes["exit_time"] = {"old": old_exit_time, "new": exit_time_str}
        else:
            entry.exit_time = None
            if old_exit_time is not None:
                changes["exit_time"] = {"old": old_exit_time, "new": None}

        # Handle start_time for backup roles
        start_time_str = request.form.get("start_time")
        if start_time_str is not None:  # Only update if field was submitted
            if start_time_str:
                entry.start_time = datetime.strptime(start_time_str, "%H:%M").time()  # noqa: DTZ007
                if old_start_time != start_time_str:
                    changes["start_time"] = {
                        "old": old_start_time,
                        "new": start_time_str,
                    }
            else:
                entry.start_time = None
                if old_start_time is not None:
                    changes["start_time"] = {"old": old_start_time, "new": None}

        db.session.commit()

        # Log the action with enhanced details
        if changes:
            resident_name = (
                entry.resident.name if entry.resident else str(entry.resident_id)
            )
            role_name = entry.role.name if entry.role else str(entry.role_id)
            log_update(
                "TimeEntry",
                entry.id,
                changes=changes,
                details={
                    "entry_id": entry.id,
                    "resident": resident_name,
                    "role": role_name,
                    "date": entry.date.strftime("%Y-%m-%d"),
                },
            )

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

    if not (is_admin() or is_first_call(sheet_date)):
        flash("Only the first call resident or an admin can delete entries.", "error")
        return redirect(
            url_for("sheets.view", date_str=sheet_date.strftime("%Y-%m-%d"))
        )

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot delete entry - sheet is locked", "error")
        date_str = sheet_date.strftime("%Y-%m-%d")
        redirect_url = url_for("sheets.view", date_str=date_str)
        return redirect(redirect_url)

    try:
        # Log before deleting
        resident_name = (
            entry.resident.name if entry.resident else str(entry.resident_id)
        )
        role_name = entry.role.name if entry.role else str(entry.role_id)
        log_delete(
            "TimeEntry",
            entry.id,
            {
                "entry_id": entry.id,
                "date": str(entry.date),
                "resident": resident_name,
                "role": role_name,
                "exit_time": entry.exit_time.strftime("%H:%M")
                if entry.exit_time
                else None,
                "start_time": entry.start_time.strftime("%H:%M")
                if entry.start_time
                else None,
            },
        )

        db.session.delete(entry)
        db.session.commit()
        flash("Entry deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting entry: {e!s}", "error")

    return redirect(url_for("sheets.view", date_str=sheet_date.strftime("%Y-%m-%d")))
