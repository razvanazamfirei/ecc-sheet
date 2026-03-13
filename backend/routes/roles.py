"""Role management routes."""

import logging
from logging import Logger

from flask import Blueprint, abort, flash, render_template, request

from ..audit import log_update_strict
from ..auth import admin_required
from ..models import Role, db
from ._helpers import diff_snapshots, redirect_to

bp: Blueprint = Blueprint("roles", __name__, url_prefix="/roles")
logger: Logger = logging.getLogger(__name__)


def _role_snapshot(role: Role) -> dict[str, int | bool | None]:
    """Return the role fields tracked in update audit logs."""
    return {
        "cutoff_hour": role.cutoff_hour,
        "cutoff_minute": role.cutoff_minute,
        "is_backup": role.is_backup,
    }


def _parse_role_form() -> dict[str, int | bool]:
    """Parse and validate role form fields."""
    try:
        cutoff_hour = int(request.form.get("cutoff_hour", 17))
        cutoff_minute = int(request.form.get("cutoff_minute", 30))
    except ValueError as exc:
        raise ValueError("Cutoff hour and minute must be whole numbers.") from exc
    if not (0 <= cutoff_hour <= 23):
        raise ValueError("Hour must be between 0 and 23")
    if not (0 <= cutoff_minute <= 59):
        raise ValueError("Minute must be between 0 and 59")
    return {
        "cutoff_hour": cutoff_hour,
        "cutoff_minute": cutoff_minute,
        "is_backup": request.form.get("is_backup") == "on",
    }


@bp.route("/")
@admin_required
def index():
    """Manage roles."""
    all_roles = Role.query.order_by(Role.display_order).all()
    return render_template("roles.html", roles=all_roles)


@bp.route("/<int:role_id>/update", methods=["POST"])
@admin_required
def update(role_id):
    """Update role cutoff time and backup status."""
    role = db.session.get(Role, role_id)
    if role is None:
        abort(404)

    try:
        before = _role_snapshot(role)
        parsed_form = _parse_role_form()
        for field, value in parsed_form.items():
            setattr(role, field, value)

        changes = diff_snapshots(before, _role_snapshot(role))
        if changes:
            log_update_strict(
                "Role",
                role.id,
                changes=changes,
                details={"name": role.name},
            )

        db.session.commit()

        flash(f"Role {role.name} updated successfully", "success")

    except ValueError as exc:
        db.session.rollback()
        flash(f"Error updating role: {exc!s}", "error")
    except Exception:
        db.session.rollback()
        logger.exception("Error updating role")
        flash("Error updating role. Check logs for details.", "error")

    return redirect_to("roles.index")
