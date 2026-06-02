"""API routes for JSON endpoints."""

from flask import Blueprint, jsonify

from ..models import Resident, Role

bp: Blueprint = Blueprint("api", __name__, url_prefix="/api")


@bp.route("/residents/active")
def active_residents():
    """API endpoint to get active residents."""
    residents = Resident.get_active()
    return jsonify([{"id": r.id, "name": r.name} for r in residents])


@bp.route("/roles")
def roles():
    """API endpoint to get all roles."""
    all_roles = Role.query.order_by(Role.display_order).all()
    return jsonify(
        [
            {
                "id": r.id,
                "name": r.name,
                "cutoff_hour": r.cutoff_hour,
                "cutoff_minute": r.cutoff_minute,
                "is_backup": r.is_backup,
            }
            for r in all_roles
        ]
    )
