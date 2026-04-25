"""Resident management routes."""

import json
import logging
from logging import Logger

from flask import (
    Blueprint,
    current_app,
    render_template,
)
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from ..audit import log_create, log_update
from ..auth import admin_required, get_current_user, is_admin, is_first_call
from ..models import AuditLog, Resident, TimeEntry, db
from ..payroll_audit import filter_payroll_resident_changes
from ..staff_import import import_staff_list
from ._forms import (
    form_text,
    optional_form_int,
    optional_form_iso_date,
    optional_form_text,
)
from ._helpers import commit_flash_redirect, diff_snapshots, flash_redirect

bp: Blueprint = Blueprint("residents", __name__, url_prefix="/residents")
logger: Logger = logging.getLogger(__name__)
SAFE_STAFF_IMPORT_ERRORS = frozenset({
    "No staff records found in import",
    "Failed to fetch staff list from Amion.",
    "Staff import failed.",
})


def _resident_snapshot(resident: Resident) -> dict[str, str | int | None]:
    """Return the resident fields tracked in edit audit logs."""
    return {
        "name": resident.name,
        "first_name": resident.first_name,
        "last_name": resident.last_name,
        "class_year": resident.class_year,
        "email": resident.email,
        "phone": resident.phone,
        "abbreviation": resident.abbreviation,
        "lawson_id": resident.lawson_id,
        "hire_date": resident.hire_date.isoformat() if resident.hire_date else None,
    }


def _staff_import_error_message(error: str | None) -> str:
    """Return a sanitized user-facing staff import error."""
    if error and error in SAFE_STAFF_IMPORT_ERRORS:
        return error
    return "Staff list import failed."


def _create_resident(name: str) -> Resident:
    """Create a resident and persist the matching audit log."""
    resident = Resident(name=name)
    db.session.add(resident)
    db.session.flush()
    log_create("Resident", resident.id, {"name": name})
    return resident


def _toggle_resident_active(resident: Resident) -> str:
    """Toggle a resident's active status and return the resulting verb."""
    previous_active = resident.active
    resident.active = not resident.active
    log_update(
        "Resident",
        resident.id,
        changes={"active": {"old": previous_active, "new": resident.active}},
    )
    return "activated" if resident.active else "deactivated"


def _apply_resident_form_updates(resident: Resident, *, name: str) -> None:
    """Apply the editable resident form fields to the model."""
    resident.name = name
    resident.first_name = optional_form_text("first_name")
    resident.last_name = optional_form_text("last_name")
    resident.class_year = optional_form_text("class_year")
    resident.email = optional_form_text("email")
    resident.phone = optional_form_text("phone")
    resident.abbreviation = optional_form_text("abbreviation")
    resident.lawson_id = optional_form_int("lawson_id")
    resident.hire_date = optional_form_iso_date("hire_date")


def _json_detail_fragment(field: str, value: str | int) -> str:
    """Return the serialized JSON fragment for a single audit-detail field."""
    return json.dumps({field: value})[1:-1]


def _resident_time_entry_audit_filter(resident: Resident):
    """Return the audit-log filter matching time-entry logs for a resident."""
    resident_id_fragment = _json_detail_fragment("resident_id", resident.id)
    resident_name_fragment = _json_detail_fragment("resident", resident.name)
    return (AuditLog.entity_type == "TimeEntry") & or_(
        AuditLog.details.contains(f"{resident_id_fragment},"),
        AuditLog.details.contains(f"{resident_id_fragment}}}"),
        AuditLog.details.contains(resident_name_fragment),
    )


def _resident_audit_logs(resident: Resident) -> list[AuditLog]:
    """Return recent audit activity for a resident profile."""
    return (
        AuditLog.query
        .filter(
            or_(
                (AuditLog.entity_type == "Resident")
                & (AuditLog.entity_id == resident.id),
                _resident_time_entry_audit_filter(resident),
            )
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(50)
        .all()
    )


@bp.route("/")
@admin_required
def index():
    """Manage residents."""
    all_residents = Resident.query.order_by(Resident.name).all()
    return render_template("residents.html", residents=all_residents)


@bp.route("/add", methods=["POST"])
@admin_required
def add():
    """Add a new resident."""
    name = form_text("name")

    if not name:
        return flash_redirect("residents.index", "Resident name is required", "error")

    return commit_flash_redirect(
        lambda: _create_resident(name),
        endpoint="residents.index",
        logger=logger,
        errors=(
            "Error adding resident",
            "Error adding resident. Check logs for details.",
        ),
        success_message=f"Resident {name} added successfully",
    )


@bp.route("/<int:resident_id>/toggle", methods=["POST"])
@admin_required
def toggle(resident_id):
    """Toggle resident active status."""
    resident = db.get_or_404(Resident, resident_id)

    return commit_flash_redirect(
        lambda: _toggle_resident_active(resident),
        endpoint="residents.index",
        logger=logger,
        errors=(
            "Error toggling resident status",
            "Error updating resident. Check logs for details.",
        ),
        success_message=lambda state: f"Resident {resident.name} {state}",
    )


@bp.route("/<int:resident_id>/edit", methods=["GET"])
@admin_required
def edit(resident_id):
    """Edit a resident's details."""
    resident = db.get_or_404(Resident, resident_id)
    return render_template(
        "resident_edit.html", resident=resident, class_years=Resident.CLASS_YEARS
    )


@bp.route("/<int:resident_id>/edit", methods=["POST"])
@admin_required
def edit_save(resident_id):
    """Save resident details."""
    resident = db.get_or_404(Resident, resident_id)

    name = form_text("name")
    if not name:
        return flash_redirect("residents.index", "Resident name is required.", "error")

    before = _resident_snapshot(resident)

    try:
        _apply_resident_form_updates(resident, name=name)
    except ValueError:
        current_app.logger.debug(
            "Invalid resident edit input for resident %s",
            resident_id,
            exc_info=True,
        )
        return flash_redirect(
            "residents.index",
            "Invalid input: please check the fields and try again.",
            "error",
        )

    after = _resident_snapshot(resident)
    changes = diff_snapshots(before, after)
    payroll_changes = filter_payroll_resident_changes(changes)

    if not changes:
        return flash_redirect("residents.index", "No changes to save.", "info")

    return commit_flash_redirect(
        lambda: (
            log_update("Resident", resident.id, changes=payroll_changes)
            if payroll_changes
            else None
        ),
        endpoint="residents.index",
        logger=logger,
        errors=(
            "Error saving resident",
            "Error updating resident. Check logs for details.",
        ),
        success_message=f"Resident {resident.name} updated successfully.",
    )


@bp.route("/<int:resident_id>/profile")
def profile(resident_id):
    """View resident profile page. Accessible to all users."""
    resident = db.get_or_404(Resident, resident_id)

    show_sensitive_fields = is_admin()
    show_hours = is_admin() or is_first_call()
    show_audit = is_admin()

    recent_entries = (
        TimeEntry.query
        .filter_by(resident_id=resident_id)
        .options(selectinload(TimeEntry.role))
        .order_by(TimeEntry.date.desc())
        .limit(50)
        .all()
        if show_hours
        else None
    )

    audit_logs = _resident_audit_logs(resident) if show_audit else None

    return render_template(
        "resident_profile.html",
        resident=resident,
        show_sensitive_fields=show_sensitive_fields,
        show_hours=show_hours,
        show_audit=show_audit,
        recent_entries=recent_entries,
        audit_logs=audit_logs,
    )


@bp.route("/import", methods=["POST"])
@admin_required
def import_staff():
    """Import staff list from Amion to populate resident information."""
    try:
        # Get schedule code from config
        schedule_code = current_app.config.get("AMION_SCHEDULE_CODE", "upennane")

        result = import_staff_list(schedule_code=schedule_code, user=get_current_user())

        if result["success"]:
            return flash_redirect(
                "residents.index",
                f"Staff list imported successfully: "
                f"{result['created']} created, "
                f"{result['updated']} updated, "
                f"{result['skipped']} skipped",
                "success",
            )
        return flash_redirect(
            "residents.index",
            _staff_import_error_message(result.get("error")),
            "error",
        )
    except Exception:
        logger.exception("Error importing staff list")
        return flash_redirect("residents.index", "Error importing staff list.", "error")
