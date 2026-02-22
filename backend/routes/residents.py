"""Resident management routes."""

import logging
from datetime import date
from logging import Logger

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.orm import selectinload

from ..audit import log_update
from ..auth import admin_required, get_current_user, is_admin, is_first_call
from ..models import AuditLog, Resident, TimeEntry, db
from ..staff_import import import_staff_list
from ..utils import handle_db_error

bp: Blueprint = Blueprint("residents", __name__, url_prefix="/residents")
logger: Logger = logging.getLogger(__name__)


@bp.route("/")
@admin_required
def index():
    """Manage residents."""
    all_residents = Resident.query.order_by(Resident.name).all()
    return render_template("residents.html", residents=all_residents)


@bp.route("/add", methods=["POST"])
@admin_required
@handle_db_error
def add():
    """Add a new resident."""
    name = request.form.get("name", "").strip()

    if not name:
        flash("Resident name is required", "error")
        return redirect(url_for("residents.index"))

    try:
        resident = Resident(name=name)
        db.session.add(resident)
        db.session.commit()
        flash(f"Resident {name} added successfully", "success")

    except Exception:
        db.session.rollback()
        logger.exception("Error adding resident")
        flash("Error adding resident. Check logs for details.", "error")

    return redirect(url_for("residents.index"))


@bp.route("/<int:resident_id>/toggle", methods=["POST"])
@admin_required
@handle_db_error
def toggle(resident_id):
    """Toggle resident active status."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

    try:
        resident.active = not resident.active
        db.session.commit()
        status = "activated" if resident.active else "deactivated"
        flash(f"Resident {resident.name} {status}", "success")

    except Exception:
        db.session.rollback()
        logger.exception("Error toggling resident status")
        flash("Error updating resident. Check logs for details.", "error")

    return redirect(url_for("residents.index"))


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
@handle_db_error
def edit_save(resident_id):
    """Save resident details."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

    before = {
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

    resident.name = request.form.get("name", "").strip() or resident.name
    resident.first_name = request.form.get("first_name", "").strip() or None
    resident.last_name = request.form.get("last_name", "").strip() or None

    class_year_val = request.form.get("class_year", "").strip()
    resident.class_year = class_year_val or None

    resident.email = request.form.get("email", "").strip() or None
    resident.phone = request.form.get("phone", "").strip() or None
    resident.abbreviation = request.form.get("abbreviation", "").strip() or None

    lawson_val = request.form.get("lawson_id", "").strip()
    try:
        resident.lawson_id = int(lawson_val) if lawson_val else None
    except ValueError:
        resident.lawson_id = None

    hire_date_val = request.form.get("hire_date", "").strip()
    if hire_date_val:
        try:
            resident.hire_date = date.fromisoformat(hire_date_val)
        except ValueError:
            resident.hire_date = None
    else:
        resident.hire_date = None

    after = {
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
    changes = {
        field: {"before": before[field], "after": after[field]}
        for field in before
        if before[field] != after[field]
    }

    if not changes:
        flash("No changes to save.", "info")
        return redirect(url_for("residents.index"))

    try:
        db.session.commit()
        log_update("Resident", resident.id, changes=changes)
        flash(f"Resident {resident.name} updated successfully.", "success")
    except Exception:
        db.session.rollback()
        logger.exception("Error saving resident")
        flash("Error updating resident. Check logs for details.", "error")

    return redirect(url_for("residents.index"))


@bp.route("/<int:resident_id>/profile")
def profile(resident_id):
    """View resident profile page. Accessible to all users."""
    resident = db.session.get(Resident, resident_id)
    if resident is None:
        abort(404)

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

    audit_logs = (
        AuditLog.query.filter(
            AuditLog.entity_type == "Resident",
            AuditLog.entity_id == resident_id,
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
        show_hours=show_hours,
        show_audit=show_audit,
        recent_entries=recent_entries,
        audit_logs=audit_logs,
    )


@bp.route("/import", methods=["POST"])
@admin_required
@handle_db_error
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
            flash(f"Import failed: {result['error']}", "error")

    except Exception as e:
        flash(f"Error importing staff list: {e!s}", "error")

    return redirect(url_for("residents.index"))
