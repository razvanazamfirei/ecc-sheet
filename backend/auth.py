"""
Simple authorization for ECC Sheet
Uses username from environment variable to determine admin status
"""

import os
from functools import wraps

from flask import flash, redirect, session, url_for

from .utils import get_effective_date

from .models import Resident, Role, TimeEntry


def get_current_user():
    """Get current user; when MOCK_USERS_ENABLED is set, use session override."""
    if os.getenv("MOCK_USERS_ENABLED", "").lower() in {"1", "true", "yes"}:
        try:
            if "dev_user" in session:
                return session["dev_user"]
        except RuntimeError:
            pass  # No request context (e.g. CLI or tests without a request)
    return os.getenv("USER_NAME", "Admin")


def is_admin():
    """Check if current user is admin based on env var"""
    admin_users = os.getenv("ADMIN_USERS", "Admin").split(",")
    admin_users = [user.strip() for user in admin_users]
    return get_current_user() in admin_users


def get_current_resident_id():
    """Return the resident ID for the current user by name match, or None."""

    resident = Resident.query.filter_by(name=get_current_user()).first()
    return resident.id if resident else None


def is_first_call(check_date=None):
    """
    Return True if the current user is assigned to a first-call role on check_date.

    First-call roles are configured via the FIRST_CALL_ROLES env var
    (comma-separated, default "First Call"). Matching is done by resident name
    against the current USER_NAME.
    """

    if check_date is None:
        check_date = get_effective_date()

    first_call_roles = [
        r.strip()
        for r in os.getenv("FIRST_CALL_ROLES", "First Call").split(",")
        if r.strip()
    ]

    resident_id = get_current_resident_id()
    if resident_id is None:
        return False

    return (
        TimeEntry.query.join(Role)
        .filter(
            TimeEntry.resident_id == resident_id,
            TimeEntry.date == check_date,
            Role.name.in_(first_call_roles),
        )
        .first()
        is not None
    )


def admin_required(f):
    """Decorator to require admin privileges"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash("Admin privileges required to access this page.", "error")
            return redirect(url_for("sheets.index"))
        return f(*args, **kwargs)

    return decorated_function
