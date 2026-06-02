"""Development-only routes for mock user switching.

Only active when MOCK_USERS_ENABLED=true (or 1/yes) is set in the environment.
All routes return 404 in production.
"""

from flask import Blueprint, abort, redirect, request, session

from ..auth import can_escalate_to_admin, get_admin_users, mock_users_enabled
from ._forms import form_text
from ._helpers import redirect_to

bp = Blueprint("dev", __name__, url_prefix="/dev")


@bp.before_request
def require_mock_enabled():
    if not mock_users_enabled():
        abort(404)


@bp.post("/switch-user")
def switch_user():
    """Set or clear the dev session user override."""
    user = form_text("user")
    if user:
        session["dev_user"] = user
    else:
        session.pop("dev_user", None)
    if request.referrer:
        return redirect(request.referrer)
    return redirect_to("sheets.index")


@bp.get("/sign-out")
def sign_out():
    """Clear the dev session user override."""
    session.pop("dev_user", None)
    return redirect_to("sheets.index")


@bp.get("/become-admin")
def become_admin():
    """Set dev session user to the first configured admin."""
    if not can_escalate_to_admin():
        abort(403)
    admins = get_admin_users()
    session["dev_user"] = admins[0] if admins else "Admin"
    if request.referrer:
        return redirect(request.referrer)
    return redirect_to("sheets.index")
