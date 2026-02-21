"""
Simple authorization for ECC Sheet
Uses username from environment variable to determine admin status
"""

import os
from functools import wraps

from flask import flash, redirect, url_for


def get_current_user():
    """Get current user from environment variable"""
    return os.getenv("USER_NAME", "Admin")


def is_admin():
    """Check if current user is admin based on env var"""
    admin_users = os.getenv("ADMIN_USERS", "Admin").split(",")
    admin_users = [user.strip() for user in admin_users]
    return get_current_user() in admin_users


def is_payroll_admin():
    """Check if current user has payroll admin privileges."""
    payroll_admin_users = os.getenv("PAYROLL_ADMIN_USERS", "").split(",")
    payroll_admin_users = [u.strip() for u in payroll_admin_users if u.strip()]
    return get_current_user() in payroll_admin_users


def can_view_all_reports():
    """Return True if the current user can view reports for all residents."""
    return is_admin() or is_payroll_admin()


def admin_required(f):
    """Decorator to require admin privileges"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash("Admin privileges required to access this page.", "error")
            return redirect(url_for("sheets.index"))
        return f(*args, **kwargs)

    return decorated_function


def payroll_admin_required(f):
    """Decorator to require payroll admin privileges (PAYROLL_ADMIN_USERS)."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_payroll_admin():
            flash(
                "Payroll admin privileges required to modify these settings.", "error"
            )
            return redirect(url_for("sheets.index"))
        return f(*args, **kwargs)

    return decorated_function
