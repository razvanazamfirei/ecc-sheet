"""Audit log routes."""

from flask import Blueprint, render_template, request

from backend.auth import admin_required
from backend.models import AuditLog

bp = Blueprint("audit", __name__)


@bp.route("/audit")
@admin_required
def index():
    """View audit trail."""
    # Get filter parameters
    limit = request.args.get("limit", 100, type=int)
    entity_type = request.args.get("entity_type")
    action = request.args.get("action")

    # Build query
    query = AuditLog.query
    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if action:
        query = query.filter_by(action=action)

    # Get entries
    entries = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return render_template("audit.html", entries=entries, limit=limit)
