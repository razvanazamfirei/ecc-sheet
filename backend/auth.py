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


def admin_required(f):
    """Decorator to require admin privileges"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            flash("Admin privileges required to access this page.", "error")
            return redirect(url_for("roles.index"))
        return f(*args, **kwargs)

    return decorated_function
