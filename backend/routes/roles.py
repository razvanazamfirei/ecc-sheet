"""Role management routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..auth import admin_required
from ..models import Role, db
from ..utils import handle_db_error

bp = Blueprint("roles", __name__, url_prefix="/roles")


@bp.route("/")
@admin_required
def index():
    """Manage roles."""
    all_roles = Role.query.order_by(Role.display_order).all()
    return render_template("roles.html", roles=all_roles)


@bp.route("/<int:role_id>/update", methods=["POST"])
@admin_required
@handle_db_error
def update(role_id):
    """Update role cutoff time and backup status."""
    role = Role.query.get_or_404(role_id)

    try:
        cutoff_hour = int(request.form.get("cutoff_hour", 17))
        cutoff_minute = int(request.form.get("cutoff_minute", 30))
        is_backup = request.form.get("is_backup") == "on"

        # Validate ranges
        if not (0 <= cutoff_hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        if not (0 <= cutoff_minute <= 59):
            raise ValueError("Minute must be between 0 and 59")

        role.cutoff_hour = cutoff_hour
        role.cutoff_minute = cutoff_minute
        role.is_backup = is_backup
        db.session.commit()
        flash(f"Role {role.name} updated successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating role: {e!s}", "error")

    return redirect(url_for("roles.index"))
