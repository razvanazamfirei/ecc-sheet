"""Entry routes for time entry management."""

import logging
from collections.abc import Mapping
from datetime import date, time

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
from sqlalchemy.orm import joinedload

from ..audit import log_create_strict, log_delete, log_update_strict
from ..auth import is_admin, is_first_call
from ..errors import ValidationError
from ..models import DailySheet, TimeEntry, db
from ..utils import _wants_json_response

bp = Blueprint("entries", __name__, url_prefix="/entries")
logger = logging.getLogger(__name__)
TIME_FIELDS = ("exit_time", "start_time")


def _parse_sheet_date_value(raw: str) -> date:
    """Parse a sheet date from an ISO date string."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValidationError("Date must use YYYY-MM-DD format.") from exc


def _parse_time_value(raw: str | None, field_label: str) -> time | None:
    """Parse a time input, raising a validation error on bad formats."""
    if not raw:
        return None

    try:
        return time.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_label} must use HH:MM format.") from exc


def _parse_add_entry_ids(
    resident_id_raw: str | None, role_id_raw: str | None
) -> tuple[int, int] | None:
    """Parse resident and role ids for a new entry."""
    if not resident_id_raw or not role_id_raw:
        return None

    try:
        return int(resident_id_raw), int(role_id_raw)
    except ValueError:
        return None


def _apply_time_field(
    entry: "TimeEntry", field: str, raw: str | None, old_str: str | None
) -> dict:
    """Set a time field on entry and return a change record if it changed."""
    if raw:
        field_label = field.replace("_", " ").capitalize()
        setattr(entry, field, _parse_time_value(raw, field_label))
        return {field: {"old": old_str, "new": raw}} if old_str != raw else {}
    setattr(entry, field, None)
    return {field: {"old": old_str, "new": None}} if old_str is not None else {}


def _entry_action_guard(
    check_date: date,
    date_str: str,
    *,
    permission_message: str,
    lock_message: str,
    force_json: bool = False,
) -> Response | tuple[Response, int] | None:
    """Validate edit permission and sheet lock state for a single entry action."""
    if not (is_admin() or is_first_call(check_date)):
        return _entry_error_response(
            permission_message,
            date_str,
            403,
            force_json=force_json,
        )

    sheet = DailySheet.query.filter_by(date=check_date).first()
    if sheet and sheet.locked:
        return _entry_error_response(
            lock_message,
            date_str,
            409,
            force_json=force_json,
        )

    return None


def _sheet_view_redirect(date_str: str) -> Response:
    """Return a redirect to the sheet view."""
    return redirect(url_for("sheets.view", date_str=date_str))


def _entry_names(entry: "TimeEntry") -> tuple[str, str]:
    """Return (resident_name, role_name), falling back to IDs if unloaded."""
    return (
        entry.resident.name if entry.resident else str(entry.resident_id),
        entry.role.name
        if entry.role
        else (str(entry.role_id) if entry.role_id else ""),
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


def _snapshot_time_fields(entry: "TimeEntry") -> dict[str, str | None]:
    """Return the current serialized time fields for an entry."""
    return {field: _format_time_value(getattr(entry, field)) for field in TIME_FIELDS}


def _present_time_updates(
    payload: Mapping[str, str | None],
) -> dict[str, str | None]:
    """Return only time fields explicitly present in a payload."""
    return {field: payload.get(field) for field in TIME_FIELDS if field in payload}


def _apply_time_updates(
    entry: "TimeEntry", requested_updates: Mapping[str, str | None]
) -> dict:
    """Apply requested time field updates and return the audit change set."""
    previous_values = _snapshot_time_fields(entry)
    changes = {}
    for field, raw_value in requested_updates.items():
        changes.update(
            _apply_time_field(entry, field, raw_value, previous_values[field])
        )
    return changes


def _log_entry_update(entry: "TimeEntry", changes: dict) -> None:
    """Persist audit logging for an updated time entry."""
    if not changes:
        return

    resident_name, role_name = _entry_names(entry)
    log_update_strict(
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


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    """Return a JSON error response."""
    return jsonify({"success": False, "message": message}), status_code


def _missing_entry_response() -> Response | tuple[Response, int]:
    """Return the appropriate response when an entry does not exist."""
    if _wants_json_response():
        return _json_error("Entry not found.", 404)
    abort(404)
    raise RuntimeError("Unreachable")


def _entry_error_response(
    message: str,
    date_str: str,
    status_code: int,
    *,
    flash_message: str | None = None,
    force_json: bool = False,
) -> Response | tuple[Response, int]:
    """Return a JSON error or flash+redirect response for sheet entry actions."""
    if force_json or _wants_json_response():
        return _json_error(message, status_code)

    flash(flash_message or message, "error")
    return _sheet_view_redirect(date_str)


def _entry_success_response(
    entry: "TimeEntry", date_str: str, message: str
) -> Response:
    """Return a JSON success payload or flash+redirect response."""
    if _wants_json_response():
        return jsonify(
            {
                "success": True,
                "message": message,
                "entry": _entry_json_payload(entry),
            }
        )

    flash(message, "success")
    return _sheet_view_redirect(date_str)


def _entry_mutation_error(
    message: str,
    date_str: str,
    *,
    status_code: int,
    flash_message: str | None = None,
    force_json: bool = False,
) -> Response | tuple[Response, int]:
    """Rollback a failed mutation and return the appropriate error response."""
    db.session.rollback()
    return _entry_error_response(
        message,
        date_str,
        status_code,
        flash_message=flash_message,
        force_json=force_json,
    )


def _entry_json_mutation_error(
    message: str,
    *,
    status_code: int,
) -> tuple[Response, int]:
    """Rollback a failed JSON mutation and return an error payload."""
    db.session.rollback()
    return _json_error(message, status_code)


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
                "time_updates": _present_time_updates(update),
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
        for entry in TimeEntry.query.filter(TimeEntry.id.in_(entry_ids))
        .options(joinedload(TimeEntry.resident), joinedload(TimeEntry.role))
        .all()
    }
    missing_entry_ids = [
        str(update["id"])
        for update in normalized_updates
        if update["id"] not in entries
    ]
    if missing_entry_ids:
        return _json_error(
            "Some entries were not found.",
            404,
        )

    for entry_date in {entry.date for entry in entries.values()}:
        if resp := _entry_action_guard(
            entry_date,
            entry_date.isoformat(),
            permission_message=(
                "Only the first call resident or an admin can update entries."
            ),
            lock_message="Cannot update entries - sheet is locked",
            force_json=True,
        ):
            return resp

    return entries


def _validated_add_entry_request():
    """Return validated add-entry form data or an error response."""
    sheet_date_str = request.form.get("date")
    if not sheet_date_str:
        flash("Date is required", "error")
        return redirect(url_for("sheets.index"))

    try:
        sheet_date = _parse_sheet_date_value(sheet_date_str)
    except ValidationError as exc:
        flash(str(exc), "error")
        return redirect(url_for("sheets.index"))

    if resp := _entry_action_guard(
        sheet_date,
        sheet_date_str,
        permission_message="Only the first call resident or an admin can add entries.",
        lock_message="Cannot add entry - sheet is locked",
    ):
        return resp

    parsed_ids = _parse_add_entry_ids(
        request.form.get("resident_id"),
        request.form.get("role_id"),
    )
    if parsed_ids is None:
        flash("Resident and role are required and must be valid IDs", "error")
        return _sheet_view_redirect(sheet_date_str)

    resident_id, role_id = parsed_ids
    return (
        sheet_date,
        sheet_date_str,
        resident_id,
        role_id,
        request.form.get("exit_time"),
        request.form.get("start_time"),
    )


@bp.route("/add", methods=["POST"])
def add():
    """Add a new time entry."""
    validated_request = _validated_add_entry_request()
    if isinstance(validated_request, Response):
        return validated_request

    (
        sheet_date,
        sheet_date_str,
        resident_id,
        role_id,
        exit_time_str,
        start_time_str,
    ) = validated_request

    try:
        exit_time = _parse_time_value(exit_time_str, "Exit time")
        start_time = _parse_time_value(start_time_str, "Start time")

        entry = TimeEntry(
            date=sheet_date,
            resident_id=resident_id,
            role_id=role_id,
            exit_time=exit_time,
            start_time=start_time,
        )

        db.session.add(entry)
        resident_name = str(resident_id)
        role_name = str(role_id)
        db.session.flush()
        if entry.resident:
            resident_name = entry.resident.name
        if entry.role:
            role_name = entry.role.name

        log_create_strict(
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
        db.session.commit()
    except ValidationError as exc:
        return _entry_mutation_error(
            str(exc),
            sheet_date_str,
            status_code=400,
            flash_message=str(exc),
        )
    except Exception:
        logger.exception("Failed to add time entry")
        return _entry_mutation_error(
            "An error occurred while adding the entry.",
            sheet_date_str,
            status_code=500,
            flash_message="An error occurred while adding the entry.",
        )

    flash("Entry added successfully", "success")
    return _sheet_view_redirect(sheet_date_str)


@bp.route("/<int:entry_id>/update", methods=["POST"])
def update(entry_id):
    """Update an existing time entry."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        return _missing_entry_response()

    sheet_date_str = entry.date.strftime("%Y-%m-%d")

    if resp := _entry_action_guard(
        entry.date,
        sheet_date_str,
        permission_message=(
            "Only the first call resident or an admin can update entries."
        ),
        lock_message="Cannot update entry - sheet is locked",
    ):
        return resp

    try:
        changes = _apply_time_updates(entry, _present_time_updates(request.form))

        if changes:
            db.session.flush()
            _log_entry_update(entry, changes)
        db.session.commit()
        response: Response | tuple[Response, int] = _entry_success_response(
            entry, sheet_date_str, "Entry updated successfully"
        )
    except ValidationError as exc:
        response = _entry_mutation_error(
            str(exc),
            sheet_date_str,
            status_code=400,
            flash_message=str(exc),
        )
    except Exception:
        logger.exception("Failed to update time entry %s", entry_id)
        response = _entry_mutation_error(
            "An error occurred while updating the entry.",
            sheet_date_str,
            status_code=500,
            flash_message="An error occurred while updating the entry.",
        )

    return response


@bp.route("/update-all", methods=["POST"])
def update_all():
    """Update multiple time entries in a single JSON request."""
    normalized_updates = _normalize_bulk_updates_payload(request.get_json(silent=True))
    if isinstance(normalized_updates, tuple):
        return normalized_updates

    entries = _load_validated_bulk_entries(normalized_updates)
    if isinstance(entries, tuple):
        return entries

    entry_updates: list[tuple[TimeEntry, dict]] = []
    try:
        for update in normalized_updates:
            entry = entries[update["id"]]
            entry_updates.append(
                (entry, _apply_time_updates(entry, update["time_updates"]))
            )

        db.session.flush()
        for entry, changes in entry_updates:
            _log_entry_update(entry, changes)
        db.session.commit()
    except ValidationError as exc:
        return _entry_json_mutation_error(str(exc), status_code=400)
    except Exception:
        logger.exception("Failed to bulk update time entries")
        return _entry_json_mutation_error(
            "An error occurred while updating entries.",
            status_code=500,
        )

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
def delete(entry_id):
    """Delete a time entry."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        abort(404)
    sheet_date = entry.date

    sheet_date_str = sheet_date.strftime("%Y-%m-%d")

    if resp := _entry_action_guard(
        sheet_date,
        sheet_date_str,
        permission_message=(
            "Only the first call resident or an admin can delete entries."
        ),
        lock_message="Cannot delete entry - sheet is locked",
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

    except Exception:
        logger.exception("Failed to delete time entry %s", entry_id)
        return _entry_mutation_error(
            "An error occurred while deleting the entry.",
            sheet_date_str,
            status_code=500,
            flash_message="An error occurred while deleting the entry.",
        )

    try:
        log_delete("TimeEntry", saved_entry_id, log_details)
    except Exception:
        logger.warning("Audit log failed for entry %s", saved_entry_id, exc_info=True)

    return _sheet_view_redirect(sheet_date_str)
