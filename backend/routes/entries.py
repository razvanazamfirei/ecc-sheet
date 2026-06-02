"""Entry routes for time entry management."""

import logging
from collections.abc import Callable, Mapping
from datetime import date, time

from flask import (
    Blueprint,
    abort,
    jsonify,
    make_response,
    request,
)
from sqlalchemy.orm import joinedload
from werkzeug.wrappers import Response

from ..audit import log_create_strict, log_delete, log_update_strict
from ..auth import is_admin, is_first_call
from ..errors import ValidationError
from ..models import DailySheet, TimeEntry, db
from ..utils import _wants_json_response
from ._forms import form_text
from ._helpers import (
    flash_redirect,
    flash_sheet_redirect,
    parse_iso_date,
)

bp = Blueprint("entries", __name__, url_prefix="/entries")
logger = logging.getLogger(__name__)
TIME_FIELDS = ("exit_time", "start_time", "anesthesia_stop_time")
type ResponseValue = Response | tuple[Response, int]


def _parse_time_value(raw: str | None, field_label: str) -> time | None:
    """Parse a time input, raising a validation error on bad formats."""
    if not raw:
        return None

    try:
        return time.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_label} must use HH:MM format.") from exc


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


def _format_time_value(raw_time) -> str | None:
    """Format a time value for inputs/JSON."""
    return raw_time.strftime("%H:%M") if raw_time else None


def _format_time_display(raw_time) -> str | None:
    """Format a time value for display."""
    return raw_time.strftime("%I:%M %p") if raw_time else None


def _entry_json_payload(entry: "TimeEntry") -> dict:
    """Return the JSON payload describing a saved entry."""
    payload = {
        "id": entry.id,
        "resident_id": entry.resident_id,
        "role_id": entry.role_id,
        "resident_name": entry.resident.name if entry.resident else "",
        "resident_url": f"/residents/{entry.resident_id}",
        "role_name": entry.role.name if entry.role else "",
        "role_is_backup": entry.role.is_backup if entry.role else False,
        "missing_exit_time": entry.exit_time is None,
        "overtime_hours": entry.overtime_hours,
        "overtime_display": f"{entry.overtime_hours:.2f} hrs",
    }
    for field in TIME_FIELDS:
        payload[field] = _format_time_value(getattr(entry, field))
        payload[f"{field}_display"] = _format_time_display(getattr(entry, field))
    return payload


def _present_time_updates(
    payload: Mapping[str, str | None],
) -> dict[str, str | None]:
    """Return only time fields explicitly present in a payload."""
    return {field: payload.get(field) for field in TIME_FIELDS if field in payload}


def _apply_time_updates(
    entry: "TimeEntry", requested_updates: Mapping[str, str | None]
) -> dict:
    """Apply requested time field updates and return the audit change set."""
    changes = {}
    for field, raw_value in requested_updates.items():
        old_value = _format_time_value(getattr(entry, field))
        if raw_value:
            setattr(
                entry,
                field,
                _parse_time_value(raw_value, field.replace("_", " ").capitalize()),
            )
            if old_value != raw_value:
                changes[field] = {"old": old_value, "new": raw_value}
            continue

        setattr(entry, field, None)
        if old_value is not None:
            changes[field] = {"old": old_value, "new": None}
    return changes


def _entry_audit_details(
    entry: "TimeEntry",
    *,
    include_times: bool = False,
) -> dict[str, int | str | None]:
    """Return a shared audit-details payload for a time entry."""
    details: dict[str, int | str | None] = {
        "entry_id": entry.id,
        "resident_id": entry.resident_id,
        "resident": entry.resident.name if entry.resident else str(entry.resident_id),
        "role": (
            entry.role.name
            if entry.role
            else (str(entry.role_id) if entry.role_id else "")
        ),
        "date": entry.date.isoformat(),
    }
    if include_times:
        details["exit_time"] = _format_time_value(entry.exit_time)
        details["start_time"] = _format_time_value(entry.start_time)
    return details


def _log_entry_update(entry: "TimeEntry", changes: dict) -> None:
    """Persist audit logging for an updated time entry."""
    if not changes:
        return

    log_update_strict(
        "TimeEntry",
        entry.id,
        changes=changes,
        details=_entry_audit_details(entry),
    )


def _json_error(message: str, status_code: int) -> tuple[Response, int]:
    """Return a JSON error response."""
    return jsonify({"success": False, "message": message}), status_code


def _entry_error_response(
    message: str,
    date_str: str = "",
    status_code: int = 400,
    *,
    flash_message: str | None = None,
    force_json: bool = False,
) -> Response | tuple[Response, int]:
    """Return a JSON error or flash+redirect response for sheet entry actions."""
    if force_json or _wants_json_response():
        return _json_error(message, status_code)

    return flash_sheet_redirect(date_str, flash_message or message, "error")


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

    return flash_sheet_redirect(date_str, message, "success")


def _entry_mutation_response[T](
    mutation: Callable[[], T],
    *,
    errors: tuple[str, str],
    success_response: Callable[[T], ResponseValue],
    date_str: str = "",
    force_json: bool = False,
) -> ResponseValue:
    """Run an entry mutation and convert the result into a response."""
    try:
        result = mutation()
        db.session.commit()
    except ValidationError as exc:
        db.session.rollback()
        return _entry_error_response(
            str(exc),
            date_str,
            status_code=400,
            flash_message=str(exc),
            force_json=force_json,
        )
    except Exception:
        db.session.rollback()
        log_message, error_message = errors
        logger.exception(log_message)
        return _entry_error_response(
            error_message,
            date_str,
            status_code=500,
            flash_message=error_message,
            force_json=force_json,
        )

    return success_response(result)


def _validated_bulk_entry_updates(  # noqa: PLR0911
    payload: object,
) -> list[tuple[TimeEntry, dict[str, str | None]]] | ResponseValue:
    """Return validated bulk updates as ordered (entry, time_updates) pairs."""
    if not isinstance(payload, dict):
        return _json_error("Invalid request payload.", 400)

    updates_raw = payload.get("entries")
    if not isinstance(updates_raw, list) or not updates_raw:
        return _json_error("No entries were provided.", 400)

    requested_updates: list[tuple[int, dict[str, str | None]]] = []
    seen_entry_ids: set[int] = set()
    for individual_update in updates_raw:
        if not isinstance(individual_update, dict):
            return _json_error("Each entry update must be an object.", 400)

        entry_id_raw = individual_update.get("id")
        try:
            if entry_id_raw is None:
                raise ValueError
            entry_id = int(str(entry_id_raw))
        except (TypeError, ValueError):
            return _json_error("Each entry update must include a valid id.", 400)

        if entry_id in seen_entry_ids:
            return _json_error("Duplicate entry ids are not allowed.", 400)
        seen_entry_ids.add(entry_id)
        requested_updates.append((entry_id, _present_time_updates(individual_update)))

    entries = {
        entry.id: entry
        for entry in TimeEntry.query.filter(TimeEntry.id.in_(seen_entry_ids))
        .options(joinedload(TimeEntry.resident), joinedload(TimeEntry.role))
        .all()
    }
    if len(entries) != len(seen_entry_ids):
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

    return [
        (entries[entry_id], time_updates)
        for entry_id, time_updates in requested_updates
    ]


def _validated_add_entry_request(  # noqa: PLR0911
) -> tuple[date, str, int, int, time | None, time | None] | Response:
    """Return validated add-entry form data or an error response."""
    sheet_date_str = form_text("date")
    if not sheet_date_str:
        return flash_redirect("sheets.index", "Date is required", "error")

    try:
        sheet_date = parse_iso_date(
            sheet_date_str,
            error_message="Date must use YYYY-MM-DD format.",
        )
    except ValueError as exc:
        return flash_redirect("sheets.index", str(exc), "error")

    # Use a normalized, server-generated ISO date string to avoid reflecting
    # potentially malicious user input back to the client.
    sheet_date_str = sheet_date.isoformat()

    if resp := _entry_action_guard(
        sheet_date,
        sheet_date_str,
        permission_message="Only the first call resident or an admin can add entries.",
        lock_message="Cannot add entry - sheet is locked",
    ):
        # _entry_action_guard may return a (Response, int) tuple for JSON callers
        return make_response(*resp) if isinstance(resp, tuple) else resp

    resident_id_raw = form_text("resident_id")
    role_id_raw = form_text("role_id")
    if not resident_id_raw or not role_id_raw:
        return flash_sheet_redirect(
            sheet_date_str,
            "Resident and role are required and must be valid IDs",
            "error",
        )
    try:
        resident_id, role_id = int(resident_id_raw), int(role_id_raw)
    except ValueError:
        return flash_sheet_redirect(
            sheet_date_str,
            "Resident and role are required and must be valid IDs",
            "error",
        )

    try:
        exit_time = _parse_time_value(form_text("exit_time"), "Exit time")
        start_time = _parse_time_value(form_text("start_time"), "Start time")
    except ValidationError as exc:
        return flash_sheet_redirect(sheet_date_str, str(exc), "error")

    return (
        sheet_date,
        sheet_date_str,
        resident_id,
        role_id,
        exit_time,
        start_time,
    )


def _create_entry(
    sheet_date: date,
    resident_id: int,
    role_id: int,
    exit_time: time | None,
    start_time: time | None,
) -> TimeEntry:
    """Create and audit-log a new time entry."""
    entry = TimeEntry(
        date=sheet_date,
        resident_id=resident_id,
        role_id=role_id,
        exit_time=exit_time,
        start_time=start_time,
    )
    db.session.add(entry)
    db.session.flush()
    log_create_strict(
        "TimeEntry",
        entry.id,
        _entry_audit_details(entry, include_times=True),
    )
    return entry


def _update_entry_record(
    entry: TimeEntry, requested_updates: Mapping[str, str | None]
) -> None:
    """Apply requested time changes and persist audit details when needed."""
    changes = _apply_time_updates(entry, requested_updates)
    if not changes:
        return

    db.session.flush()
    _log_entry_update(entry, changes)


def _apply_bulk_entry_updates(
    entry_updates: list[tuple[TimeEntry, dict[str, str | None]]],
) -> None:
    """Apply and audit-log a validated bulk update request."""
    entry_updates = [
        (entry, _apply_time_updates(entry, time_updates))
        for entry, time_updates in entry_updates
    ]

    db.session.flush()
    for entry, changes in entry_updates:
        _log_entry_update(entry, changes)


def _delete_entry_record(entry: TimeEntry) -> tuple[int, dict[str, int | str | None]]:
    """Delete an entry and return the data needed for post-commit audit logging."""
    log_details = _entry_audit_details(entry, include_times=True)
    saved_entry_id = entry.id
    db.session.delete(entry)
    return saved_entry_id, log_details


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
        exit_time,
        start_time,
    ) = validated_request

    return _entry_mutation_response(
        lambda: _create_entry(
            sheet_date,
            resident_id,
            role_id,
            exit_time,
            start_time,
        ),
        errors=(
            "Failed to add time entry",
            "An error occurred while adding the entry.",
        ),
        date_str=sheet_date_str,
        success_response=lambda entry: _entry_success_response(
            entry,
            sheet_date_str,
            "Entry added successfully",
        ),
    )


@bp.route("/<int:entry_id>/update", methods=["POST"])
def update(entry_id):
    """Update an existing time entry."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is None:
        if _wants_json_response():
            return _json_error("Entry not found.", 404)
        abort(404)

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

    return _entry_mutation_response(
        lambda: _update_entry_record(entry, _present_time_updates(request.form)),
        errors=(
            f"Failed to update time entry {entry_id}",
            "An error occurred while updating the entry.",
        ),
        date_str=sheet_date_str,
        success_response=lambda _: _entry_success_response(
            entry,
            sheet_date_str,
            "Entry updated successfully",
        ),
    )


@bp.route("/update-all", methods=["POST"])
def update_all():
    """Update multiple time entries in a single JSON request."""
    entry_updates = _validated_bulk_entry_updates(request.get_json(silent=True))
    if isinstance(entry_updates, (tuple, Response)):
        return entry_updates

    return _entry_mutation_response(
        lambda: _apply_bulk_entry_updates(entry_updates),
        errors=(
            "Failed to bulk update time entries",
            "An error occurred while updating entries.",
        ),
        force_json=True,
        success_response=lambda _: jsonify(
            {
                "success": True,
                "message": "All entries updated successfully.",
                "entries": [
                    _entry_json_payload(entry) for entry, _time_updates in entry_updates
                ],
            }
        ),
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

    def _success(result: tuple[int, dict[str, int | str | None]]) -> Response:
        saved_entry_id, log_details = result
        try:
            log_delete("TimeEntry", saved_entry_id, log_details)
        except Exception:
            logger.warning(
                "Audit log failed for entry %s",
                saved_entry_id,
                exc_info=True,
            )
        if _wants_json_response():
            return jsonify({"success": True, "message": "Entry deleted successfully"})
        return flash_sheet_redirect(
            sheet_date_str,
            "Entry deleted successfully",
            "success",
        )

    return _entry_mutation_response(
        lambda: _delete_entry_record(entry),
        errors=(
            f"Failed to delete time entry {entry_id}",
            "An error occurred while deleting the entry.",
        ),
        date_str=sheet_date_str,
        success_response=_success,
    )
