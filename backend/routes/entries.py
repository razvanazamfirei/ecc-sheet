"""Entry routes for time entry management."""

import logging
from datetime import date, datetime

from flask import Blueprint, Response, abort, flash, redirect, request, url_for

from ..audit import log_create, log_delete, log_update
from ..auth import is_admin, is_first_call
from ..models import DailySheet, TimeEntry, db
from ..utils import handle_db_error

bp = Blueprint("entries", __name__, url_prefix="/entries")
logger = logging.getLogger(__name__)


def _apply_time_field(
    entry: "TimeEntry", field: str, raw: str | None, old_str: str | None
) -> dict:
    """Set a time field on entry and return a change record if it changed."""
    if raw:
        setattr(entry, field, datetime.strptime(raw, "%H:%M").time())  # noqa: DTZ007
        return {field: {"old": old_str, "new": raw}} if old_str != raw else {}
    setattr(entry, field, None)
    return {field: {"old": old_str, "new": None}} if old_str is not None else {}


def _check_sheet_locked(
    check_date: date, date_str: str, action: str
) -> Response | None:
    """Return a redirect response if the sheet is locked, else None."""
    sheet = DailySheet.query.filter_by(date=check_date).first()
    if sheet and sheet.locked:
        flash(f"Cannot {action} - sheet is locked", "error")
        return redirect(url_for("sheets.view", date_str=date_str))
    return None


def _entry_names(entry: "TimeEntry") -> tuple[str, str]:
    """Return (resident_name, role_name), falling back to IDs if unloaded."""
    return (
        entry.resident.name if entry.resident else str(entry.resident_id),
        entry.role.name
        if entry.role
        else (str(entry.role_id) if entry.role_id else ""),
    )


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

        if resp := _check_sheet_locked(sheet_date, sheet_date_str, "add entry"):
            return resp

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
        # Resolve relationship names before commit so they are available for audit
        # logging even if the session state changes after commit.
        resident_name = str(resident_id)
        role_name = str(role_id)
        db.session.flush()
        if entry.resident:
            resident_name = entry.resident.name
        if entry.role:
            role_name = entry.role.name
        db.session.commit()

        # Log the action - wrapped separately so audit failure does not
        # roll back the committed entry or flash a false failure message.
        try:
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
        except Exception:
            logger.warning("Audit log failed for entry %s", entry.id, exc_info=True)

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

    if resp := _check_sheet_locked(
        entry.date, entry.date.strftime("%Y-%m-%d"), "update entry"
    ):
        return resp

    try:
        old_exit_time = entry.exit_time.strftime("%H:%M") if entry.exit_time else None
        old_start_time = (
            entry.start_time.strftime("%H:%M") if entry.start_time else None
        )

        changes = _apply_time_field(
            entry, "exit_time", request.form.get("exit_time"), old_exit_time
        )

        # Handle start_time for backup roles (only update if field was submitted)
        start_time_str = request.form.get("start_time")
        if start_time_str is not None:
            changes.update(
                _apply_time_field(entry, "start_time", start_time_str, old_start_time)
            )

        db.session.commit()
        flash("Entry updated successfully", "success")

        # Log the action with enhanced details
        if changes:
            try:
                resident_name, role_name = _entry_names(entry)
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
            except Exception:
                logger.warning("Audit log failed for entry %s", entry.id, exc_info=True)

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

    if resp := _check_sheet_locked(
        sheet_date, sheet_date.strftime("%Y-%m-%d"), "delete entry"
    ):
        return resp

    try:
        resident_name, role_name = _entry_names(entry)
        log_details = {
            "entry_id": entry.id,
            "date": str(entry.date),
            "resident": resident_name,
            "role": role_name,
            "exit_time": entry.exit_time.strftime("%H:%M") if entry.exit_time else None,
            "start_time": entry.start_time.strftime("%H:%M")
            if entry.start_time
            else None,
        }
        saved_entry_id = entry.id
        db.session.delete(entry)
        db.session.commit()
        flash("Entry deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting entry: {e!s}", "error")
        return redirect(
            url_for("sheets.view", date_str=sheet_date.strftime("%Y-%m-%d"))
        )

    try:
        log_delete("TimeEntry", saved_entry_id, log_details)
    except Exception:
        logger.warning("Audit log failed for entry %s", saved_entry_id, exc_info=True)

    return redirect(url_for("sheets.view", date_str=sheet_date.strftime("%Y-%m-%d")))
