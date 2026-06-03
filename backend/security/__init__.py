"""Authentication and SAML security helpers."""

from backend.security.auth import (
    admin_required,
    can_filter_reports_by_resident,
    can_view_all_reports,
    get_admin_users,
    get_current_resident_id,
    get_current_user,
    get_first_call_role_names,
    get_payroll_admin_users,
    is_admin,
    is_first_call,
    is_payroll_admin,
    mock_users_enabled,
    payroll_admin_required,
)

__all__ = [
    "admin_required",
    "can_filter_reports_by_resident",
    "can_view_all_reports",
    "get_admin_users",
    "get_current_resident_id",
    "get_current_user",
    "get_first_call_role_names",
    "get_payroll_admin_users",
    "is_admin",
    "is_first_call",
    "is_payroll_admin",
    "mock_users_enabled",
    "payroll_admin_required",
]
