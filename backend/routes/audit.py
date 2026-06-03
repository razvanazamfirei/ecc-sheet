"""Audit log routes."""

from flask import Blueprint, render_template, request

from backend.audit import get_audit_trail
from backend.security import admin_required

bp = Blueprint("audit", __name__)


@bp.route("/audit")
@admin_required
def index():
    """View audit trail."""
    limit = request.args.get("limit", 100, type=int)
    entity_type = request.args.get("entity_type")
    action = request.args.get("action")
    entries = get_audit_trail(entity_type=entity_type, action=action, limit=limit)

    return render_template("audit.html", entries=entries, limit=limit)
