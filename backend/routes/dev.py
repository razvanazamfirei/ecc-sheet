"""Development-only routes for mock user switching.

Only active when MOCK_USERS_ENABLED=true (or 1/yes) is set in the environment.
All routes return 404 in production.
"""

import os

from flask import Blueprint, abort, redirect, request, session, url_for

bp = Blueprint("dev", __name__, url_prefix="/dev")


def _mock_enabled() -> bool:
    return os.getenv("MOCK_USERS_ENABLED", "").lower() in {"1", "true", "yes"}


@bp.before_request
def require_mock_enabled():
    if not _mock_enabled():
        abort(404)


@bp.post("/switch-user")
def switch_user():
    """Set or clear the dev session user override."""
    user = request.form.get("user", "").strip()
    if user:
        session["dev_user"] = user
    else:
        session.pop("dev_user", None)
    return redirect(request.referrer or url_for("sheets.index"))
