"""Role management routes."""

import logging
from logging import Logger

from flask import Blueprint, abort, render_template, request

from backend.audit import log_update_strict
from backend.models import Role, db
from backend.routes._forms import form_text
from backend.routes._helpers import (
    commit_flash_redirect,
    diff_snapshots,
    flash_redirect,
)
from backend.security import admin_required

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
        cutoff_hour = int(
            form_text("cutoff_hour") if "cutoff_hour" in request.form else "17"
        )
        cutoff_minute = int(
            form_text("cutoff_minute") if "cutoff_minute" in request.form else "30"
        )
    except ValueError as exc:
        raise ValueError("Cutoff hour and minute must be whole numbers.") from exc
    if not (0 <= cutoff_hour <= 23):
        raise ValueError("Hour must be between 0 and 23")
    if not (0 <= cutoff_minute <= 59):
        raise ValueError("Minute must be between 0 and 59")
    return {
        "cutoff_hour": cutoff_hour,
        "cutoff_minute": cutoff_minute,
        "is_backup": form_text("is_backup") == "on",
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
        parsed_form = _parse_role_form()
    except ValueError as exc:
        return flash_redirect("roles.index", f"Error updating role: {exc!s}", "error")

    def _save() -> None:
        before = _role_snapshot(role)
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

    return commit_flash_redirect(
        _save,
        endpoint="roles.index",
        logger=logger,
        errors=("Error updating role", "Error updating role. Check logs for details."),
        success_message=f"Role {role.name} updated successfully",
    )
