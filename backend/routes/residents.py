"""Resident management routes."""

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

from ..auth import admin_required, get_current_user
from ..models import Resident, db
from ..staff_import import import_staff_list
from ..utils import handle_db_error

bp = Blueprint("residents", __name__, url_prefix="/residents")


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

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding resident: {e!s}", "error")

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

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating resident: {e!s}", "error")

    return redirect(url_for("residents.index"))


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
