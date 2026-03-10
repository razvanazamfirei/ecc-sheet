"""Entry routes for time entry management."""

import logging
from datetime import date, datetime

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)

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


def _wants_json_response() -> bool:
    """Return True when the caller expects a JSON response."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("X-Expect-JSON") == "1"
        or "application/json" in request.headers.get("Accept", "")
    )


def _format_time_value(raw_time) -> str | None:
    """Format a time value for inputs/JSON."""
    return raw_time.strftime("%H:%M") if raw_time else None


def _format_time_display(raw_time) -> str | None:
    """Format a time value for display."""
    return raw_time.strftime("%I:%M %p") if raw_time else None


def _entry_json_payload(entry: "TimeEntry") -> dict:
    """Return the JSON payload describing a saved entry."""
    return {
        "id": entry.id,
        "resident_id": entry.resident_id,
        "role_id": entry.role_id,
        "exit_time": _format_time_value(entry.exit_time),
        "exit_time_display": _format_time_display(entry.exit_time),
        "start_time": _format_time_value(entry.start_time),
        "start_time_display": _format_time_display(entry.start_time),
        "missing_exit_time": entry.exit_time is None,
        "overtime_hours": entry.overtime_hours,
        "overtime_display": f"{entry.overtime_hours:.2f} hrs",
    }


def _log_entry_update(entry: "TimeEntry", changes: dict) -> None:
    """Persist audit logging for an updated time entry."""
    if not changes:
        return

    try:
        resident_name, role_name = _entry_names(entry)
        log_update(
            "TimeEntry",
            entry.id,
            changes=changes,
            details={
                "entry_id": entry.id,
                "resident_id": entry.resident_id,
                "resident": resident_name,
                "role": role_name,
                "date": entry.date.strftime("%Y-%m-%d"),
            },
        )
    except Exception:
        logger.warning("Audit log failed for entry %s", entry.id, exc_info=True)


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    """Return a JSON error response."""
    return jsonify({"success": False, "message": message}), status_code


def _missing_entry_response() -> Response | tuple[Response, int]:
    """Return the appropriate response when an entry does not exist."""
    if _wants_json_response():
        return _json_error("Entry not found.", 404)
    abort(404)
    raise RuntimeError("Unreachable")


def _update_denied_response(
    message: str, date_str: str, status_code: int
) -> Response | tuple[Response, int]:
    """Return either a JSON error or a redirect for blocked updates."""
    if _wants_json_response():
        return _json_error(message, status_code)

    flash(message, "error")
    return redirect(url_for("sheets.view", date_str=date_str))


def _normalize_bulk_updates_payload(
    payload: object,
) -> list[dict] | tuple[Response, int]:
    """Validate and normalize a bulk update request payload."""
    if not isinstance(payload, dict):
        return _json_error("Invalid request payload.", 400)

    updates_raw = payload.get("entries")
    if not isinstance(updates_raw, list) or not updates_raw:
        return _json_error("No entries were provided.", 400)

    normalized_updates = []
    seen_entry_ids: set[int] = set()
    for update in updates_raw:
        if not isinstance(update, dict):
            return _json_error("Each entry update must be an object.", 400)

        entry_id_raw = update.get("id")
        try:
            entry_id = int(entry_id_raw)
        except (TypeError, ValueError):
            return _json_error("Each entry update must include a valid id.", 400)

        if entry_id in seen_entry_ids:
            return _json_error("Duplicate entry ids are not allowed.", 400)
        seen_entry_ids.add(entry_id)

        normalized_updates.append(
            {
                "id": entry_id,
                "exit_time": update.get("exit_time"),
                "has_start_time": "start_time" in update,
                "start_time": update.get("start_time"),
            }
        )

    return normalized_updates


def _load_validated_bulk_entries(
    normalized_updates: list[dict],
) -> dict[int, TimeEntry] | tuple[Response, int]:
    """Load bulk-update entries and validate access for all touched dates."""
    entry_ids = {update["id"] for update in normalized_updates}
    entries = {
        entry.id: entry
        for entry in TimeEntry.query.filter(TimeEntry.id.in_(entry_ids)).all()
    }
    missing_entry_ids = [
        str(update["id"])
        for update in normalized_updates
        if update["id"] not in entries
    ]
    if missing_entry_ids:
        return _json_error(
            "Entries not found: " + ", ".join(missing_entry_ids) + ".",
            404,
        )

    for entry_date in {entry.date for entry in entries.values()}:
        if not (is_admin() or is_first_call(entry_date)):
            return _json_error(
                "Only the first call resident or an admin can update entries.",
                403,
            )

        sheet = DailySheet.query.filter_by(date=entry_date).first()
        if sheet and sheet.locked:
            return _json_error("Cannot update entries - sheet is locked", 409)

    return entries


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
                    "resident_id": resident_id,
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
        return _missing_entry_response()

    sheet_date_str = entry.date.strftime("%Y-%m-%d")

    if not (is_admin() or is_first_call(entry.date)):
        return _update_denied_response(
            "Only the first call resident or an admin can update entries.",
            sheet_date_str,
            403,
        )

    if resp := _check_sheet_locked(entry.date, sheet_date_str, "update entry"):
        if _wants_json_response():
            return _json_error("Cannot update entry - sheet is locked", 409)
        return resp

    response: Response | tuple[Response, int]
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
        if _wants_json_response():
            response = jsonify(
                {
                    "success": True,
                    "message": "Entry updated successfully",
                    "entry": _entry_json_payload(entry),
                }
            )
        else:
            flash("Entry updated successfully", "success")
            response = redirect(url_for("sheets.view", date_str=sheet_date_str))

        _log_entry_update(entry, changes)

    except Exception as e:
        db.session.rollback()
        if _wants_json_response():
            response = _json_error(f"Error updating entry: {e!s}", 400)
        else:
            flash(f"Error updating entry: {e!s}", "error")
            response = redirect(url_for("sheets.view", date_str=sheet_date_str))

    return response


@bp.route("/update-all", methods=["POST"])
@handle_db_error
def update_all():
    """Update multiple time entries in a single JSON request."""
    normalized_updates = _normalize_bulk_updates_payload(request.get_json(silent=True))
    if isinstance(normalized_updates, tuple):
        return normalized_updates

    entries = _load_validated_bulk_entries(normalized_updates)
    if isinstance(entries, tuple):
        return entries

    entry_updates: list[tuple[TimeEntry, dict]] = []
    for update in normalized_updates:
        entry = entries[update["id"]]
        old_exit_time = entry.exit_time.strftime("%H:%M") if entry.exit_time else None
        old_start_time = (
            entry.start_time.strftime("%H:%M") if entry.start_time else None
        )

        changes = _apply_time_field(
            entry,
            "exit_time",
            update["exit_time"],
            old_exit_time,
        )

        if update["has_start_time"]:
            changes.update(
                _apply_time_field(
                    entry,
                    "start_time",
                    update["start_time"],
                    old_start_time,
                )
            )

        entry_updates.append((entry, changes))

    db.session.commit()

    for entry, changes in entry_updates:
        _log_entry_update(entry, changes)

    return jsonify(
        {
            "success": True,
            "message": "All entries updated successfully.",
            "entries": [
                _entry_json_payload(entries[update["id"]])
                for update in normalized_updates
            ],
        }
    )


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
            "resident_id": entry.resident_id,
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
