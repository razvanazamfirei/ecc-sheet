"""
Simple authorization for ECC Sheet
Uses username from environment variable to determine admin status
"""

import os
from collections.abc import Callable
from datetime import date
from functools import wraps
from typing import Any

from flask import (
    current_app,
    flash,
    has_app_context,
    has_request_context,
    redirect,
    request,
    session,
    url_for,
)

from backend.env_utils import env_csv, env_flag
from backend.models import Resident, Role, TimeEntry
from backend.saml import get_session_authenticated_user, saml_enabled
from backend.utils import get_effective_date


def _proxy_header_name() -> str:
    """Return the configured proxy auth header name."""
    if has_app_context():
        return str(current_app.config.get("AUTH_PROXY_USERNAME_HEADER") or "").strip()
    return os.getenv("AUTH_PROXY_USERNAME_HEADER", "").strip()


def get_current_user() -> str:
    """Get current user from mock session, SAML session, proxy auth, or env."""
    if mock_users_enabled():
        try:
            if "dev_user" in session:
                return session["dev_user"]
        except RuntimeError:
            pass  # No request context (e.g. CLI or tests without a request)

    if saml_enabled():
        authenticated_user = get_session_authenticated_user()
        if authenticated_user:
            return authenticated_user
        if has_request_context():
            return ""

    proxy_header = _proxy_header_name()
    if proxy_header:
        try:
            proxy_user = request.headers.get(proxy_header, "").strip()
        except RuntimeError:
            proxy_user = ""
        if proxy_user:
            return proxy_user
        if has_request_context():
            return ""

    return os.getenv("USER_NAME", "Admin")


def is_admin() -> bool:
    """Check if current user is admin based on env var"""
    return get_current_user() in get_admin_users()


def get_admin_users() -> list[str]:
    """Return the configured admin usernames."""
    return env_csv("ADMIN_USERS", "Admin")


def get_current_resident_id() -> int | None:
    """Return the resident ID for the current user.

    Matching is abbreviation-first for SSO identities (e.g. Azure `Identity`),
    with fallbacks for legacy/dev configurations.
    """
    user = get_current_user().strip()
    if not user:
        return None

    resident: Resident | None = Resident.query.filter_by(abbreviation=user).first()
    if resident is None and "@" in user:
        resident = Resident.query.filter_by(email=user).first()
    if resident is None:
        resident = Resident.query.filter_by(name=user).first()
    return resident.id if resident else None


def is_first_call(check_date: date | None = None) -> bool:
    """
    Return True if the current user is assigned to a first-call role on check_date.

    First-call roles are configured via the FIRST_CALL_ROLES env var
    (comma-separated, default "First Call"). Matching is done by resident name
    against the current USER_NAME.
    """

    if check_date is None:
        check_date = get_effective_date()

    resident_id = get_current_resident_id()
    if resident_id is None:
        return False

    return (
        TimeEntry.query.join(Role)
        .filter(
            TimeEntry.resident_id == resident_id,
            TimeEntry.date == check_date,
            Role.name.in_(get_first_call_role_names()),
        )
        .first()
        is not None
    )


def is_payroll_admin() -> bool:
    """Check if current user has payroll admin privileges."""
    return get_current_user() in get_payroll_admin_users()


def get_first_call_role_names() -> list[str]:
    """Return configured first-call role names."""
    return env_csv("FIRST_CALL_ROLES", "First Call")


def get_payroll_admin_users() -> list[str]:
    """Return the configured payroll admin usernames."""
    return env_csv("PAYROLL_ADMIN_USERS")


def mock_users_enabled() -> bool:
    """Return True when dev mock-user switching is enabled."""
    return env_flag("MOCK_USERS_ENABLED")


def can_view_all_reports() -> bool:
    """Return True if the current user can use extended report actions."""
    return is_admin() or is_payroll_admin()


def can_filter_reports_by_resident() -> bool:
    """Return True if the current user can choose any resident in reports."""
    if can_view_all_reports():
        return True

    allowed_users = env_csv("REPORT_VIEW_ALL_USERS")
    return "*" in allowed_users or get_current_user() in allowed_users


def _access_denied_redirect(endpoint: str, message: str) -> Any:
    """Flash an authorization error and redirect to a safe endpoint."""
    flash(message, "error")
    return redirect(url_for(endpoint))


def _require_access(
    check: Callable[[], bool],
    *,
    message: str,
    endpoint: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator enforcing an access check with a redirect fallback."""

    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            if not check():
                return _access_denied_redirect(endpoint, message)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def admin_required(f):
    """Decorator to require admin privileges"""
    return _require_access(
        is_admin,
        message="Admin privileges required to access this page.",
        endpoint="sheets.index",
    )(f)


def payroll_admin_required(f):
    """Decorator to require payroll admin privileges (PAYROLL_ADMIN_USERS)."""
    return _require_access(
        is_payroll_admin,
        message="Payroll admin privileges required to modify these settings.",
        endpoint="reports.payroll_settings",
    )(f)
