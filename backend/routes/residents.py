"""Resident management routes."""

import json
import logging
from datetime import date
from logging import Logger

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from ..audit import log_create, log_update
from ..auth import admin_required, get_current_user, is_admin, is_first_call
from ..models import AuditLog, Resident, TimeEntry, db
from ..staff_import import import_staff_list

bp: Blueprint = Blueprint("residents", __name__, url_prefix="/residents")
logger: Logger = logging.getLogger(__name__)
SAFE_STAFF_IMPORT_ERRORS = frozenset(
    {
        "No staff records found in import",
        "Failed to fetch staff list from Amion.",
        "Staff import failed.",
    }
)


def _residents_index_redirect() -> Response:
    """Return a redirect to the residents index."""
    return redirect(url_for("residents.index"))


def _form_text(key: str) -> str:
    """Return a trimmed form value."""
    return request.form.get(key, "").strip()


def _optional_form_text(key: str) -> str | None:
    """Return a trimmed optional form value."""
    return _form_text(key) or None


def _optional_form_int(key: str) -> int | None:
    """Return an optional integer form value, raising ValueError if malformed."""
    value = _form_text(key)
    if not value:
        return None
    return int(value)


def _optional_form_date(key: str) -> date | None:
    """Return an optional ISO date form value, raising ValueError if malformed."""
    value = _form_text(key)
    if not value:
        return None
    return date.fromisoformat(value)


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
    if error in SAFE_STAFF_IMPORT_ERRORS:
        return error
    return "Staff list import failed."


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
    name = _form_text("name")

    if not name:
        flash("Resident name is required", "error")
        return _residents_index_redirect()

    try:
        resident = Resident(name=name)
        db.session.add(resident)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error adding resident")
        flash("Error adding resident. Check logs for details.", "error")
        return _residents_index_redirect()

    try:
        log_create("Resident", resident.id, {"name": name})
    except Exception:
        logger.exception("Audit log failed for resident %s", resident.id)

    flash(f"Resident {name} added successfully", "success")
    return _residents_index_redirect()


@bp.route("/<int:resident_id>/toggle", methods=["POST"])
@admin_required
def toggle(resident_id):
    """Toggle resident active status."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

    previous_active = resident.active
    resident.active = not resident.active
    status = "activated" if resident.active else "deactivated"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error toggling resident status")
        flash("Error updating resident. Check logs for details.", "error")
        return _residents_index_redirect()

    try:
        log_update(
            "Resident",
            resident.id,
            changes={"active": {"old": previous_active, "new": resident.active}},
        )
    except Exception:
        logger.exception("Audit log failed for resident %s", resident.id)

    flash(f"Resident {resident.name} {status}", "success")
    return _residents_index_redirect()


@bp.route("/<int:resident_id>/edit", methods=["GET"])
@admin_required
def edit(resident_id):
    """Edit a resident's details."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)
    return render_template(
        "resident_edit.html", resident=resident, class_years=Resident.CLASS_YEARS
    )


@bp.route("/<int:resident_id>/edit", methods=["POST"])
@admin_required
def edit_save(resident_id):
    """Save resident details."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

    name = _form_text("name")
    if not name:
        flash("Resident name is required.", "error")
        return _residents_index_redirect()

    before = _resident_snapshot(resident)

    try:
        resident.name = name
        resident.first_name = _optional_form_text("first_name")
        resident.last_name = _optional_form_text("last_name")
        resident.class_year = _optional_form_text("class_year")
        resident.email = _optional_form_text("email")
        resident.phone = _optional_form_text("phone")
        resident.abbreviation = _optional_form_text("abbreviation")
        resident.lawson_id = _optional_form_int("lawson_id")
        resident.hire_date = _optional_form_date("hire_date")
    except ValueError:
        current_app.logger.debug(
            "Invalid resident edit input for resident %s",
            resident_id,
            exc_info=True,
        )
        flash("Invalid input: please check the fields and try again.", "error")
        return _residents_index_redirect()

    after = _resident_snapshot(resident)
    changes = {
        field: {"old": before[field], "new": after[field]}
        for field in before
        if before[field] != after[field]
    }

    if not changes:
        flash("No changes to save.", "info")
        return _residents_index_redirect()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Error saving resident")
        flash("Error updating resident. Check logs for details.", "error")
        return _residents_index_redirect()

    try:
        log_update("Resident", resident.id, changes=changes)
    except Exception:
        logger.exception("Audit log failed for resident %s", resident.id)

    flash(f"Resident {resident.name} updated successfully.", "success")
    return _residents_index_redirect()


@bp.route("/<int:resident_id>/profile")
def profile(resident_id):
    """View resident profile page. Accessible to all users."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

    show_sensitive_fields = is_admin()
    show_hours = is_admin() or is_first_call()
    show_audit = is_admin()

    recent_entries = (
        TimeEntry.query.filter_by(resident_id=resident_id)
        .options(selectinload(TimeEntry.role))
        .order_by(TimeEntry.date.desc())
        .limit(50)
        .all()
        if show_hours
        else None
    )

    resident_id_mid_fragment = f'"resident_id": {resident_id},'
    resident_id_end_fragment = f'"resident_id": {resident_id}}}'
    resident_name_fragment = f'"resident": {json.dumps(resident.name)}'
    audit_logs = (
        AuditLog.query.filter(
            or_(
                (AuditLog.entity_type == "Resident")
                & (AuditLog.entity_id == resident_id),
                (AuditLog.entity_type == "TimeEntry")
                & (
                    AuditLog.details.contains(resident_id_mid_fragment)
                    | AuditLog.details.contains(resident_id_end_fragment)
                    | AuditLog.details.contains(resident_name_fragment)
                ),
            )
        )
        .order_by(AuditLog.timestamp.desc())
        .limit(50)
        .all()
        if show_audit
        else None
    )

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
            flash(
                f"Staff list imported successfully: "
                f"{result['created']} created, "
                f"{result['updated']} updated, "
                f"{result['skipped']} skipped",
                "success",
            )
        else:
            flash(_staff_import_error_message(result.get("error")), "error")
    except Exception:
        logger.exception("Error importing staff list")
        flash("Error importing staff list.", "error")

    return _residents_index_redirect()
