"""Tests for authentication and authorization module."""

import os
from datetime import time
from unittest.mock import patch

import pytest

from backend.auth import (
    can_filter_reports_by_resident,
    get_current_user,
    is_admin,
    is_first_call,
    is_payroll_admin,
)
from backend.utils import get_effective_date


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    def test_returns_user_name_from_env(self):
        """Test that get_current_user returns USER_NAME from environment."""
        original = os.environ.get("USER_NAME")
        try:
            os.environ["USER_NAME"] = "Test User Name"
            assert get_current_user() == "Test User Name"
        finally:
            if original is not None:
                os.environ["USER_NAME"] = original
            else:
                os.environ.pop("USER_NAME", None)

    def test_returns_admin_when_not_set(self):
        """Test that get_current_user returns Admin when USER_NAME not set."""
        original = os.environ.get("USER_NAME")
        try:
            if "USER_NAME" in os.environ:
                del os.environ["USER_NAME"]
            assert get_current_user() == "Admin"
        finally:
            if original is not None:
                os.environ["USER_NAME"] = original

    def test_returns_empty_string_if_set_empty(self):
        """Test that get_current_user returns empty string if USER_NAME is empty."""
        original = os.environ.get("USER_NAME")
        try:
            os.environ["USER_NAME"] = ""
            assert not get_current_user()
        finally:
            if original is not None:
                os.environ["USER_NAME"] = original
            else:
                os.environ.pop("USER_NAME", None)

    def test_uses_proxy_header_when_configured(self, app):
        """Test proxy-auth header overrides USER_NAME inside a request context."""
        original_user = os.environ.get("USER_NAME")
        original_header = app.config.get("AUTH_PROXY_USERNAME_HEADER")
        try:
            os.environ["USER_NAME"] = "Env User"
            app.config["AUTH_PROXY_USERNAME_HEADER"] = "X-Auth-User"
            with app.test_request_context("/", headers={"X-Auth-User": "Proxy User"}):
                assert get_current_user() == "Proxy User"
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            app.config["AUTH_PROXY_USERNAME_HEADER"] = original_header or ""

    @pytest.mark.usefixtures("saml_enabled_app")
    def test_uses_session_authenticated_user_when_present(self, client):
        """Test SAML/session auth overrides USER_NAME inside requests."""
        with client.session_transaction() as sess:
            sess["auth_user"] = "Session User"

        response = client.get("/")

        assert response.status_code == 200
        assert b"Session User" in response.data

    def test_proxy_header_returns_empty_user_when_missing(self, app):
        """Test proxy-auth configuration fails closed when the header is absent."""
        original_user = os.environ.get("USER_NAME")
        original_header = app.config.get("AUTH_PROXY_USERNAME_HEADER")
        try:
            os.environ["USER_NAME"] = "Env User"
            app.config["AUTH_PROXY_USERNAME_HEADER"] = "X-Auth-User"
            with app.test_request_context("/"):
                assert not get_current_user()
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            app.config["AUTH_PROXY_USERNAME_HEADER"] = original_header or ""

    def test_proxy_auth_rejects_request_without_header(self, client, app):
        """Requests are rejected when proxy-auth is configured without a user."""
        original_header = app.config.get("AUTH_PROXY_USERNAME_HEADER")
        original_mock = os.environ.get("MOCK_USERS_ENABLED")
        try:
            app.config["AUTH_PROXY_USERNAME_HEADER"] = "X-Auth-User"
            os.environ.pop("MOCK_USERS_ENABLED", None)
            response = client.get("/")
            assert response.status_code == 401
            assert b"Authentication required" in response.data
        finally:
            app.config["AUTH_PROXY_USERNAME_HEADER"] = original_header or ""
            if original_mock is not None:
                os.environ["MOCK_USERS_ENABLED"] = original_mock
            else:
                os.environ.pop("MOCK_USERS_ENABLED", None)

    def test_proxy_auth_401_skips_schema_and_background_bootstrap(self, client, app):
        """Unauthorized proxy-auth requests should not trigger bootstrap work."""
        original_header = app.config.get("AUTH_PROXY_USERNAME_HEADER")
        original_mock = os.environ.get("MOCK_USERS_ENABLED")
        try:
            app.config["AUTH_PROXY_USERNAME_HEADER"] = "X-Auth-User"
            os.environ.pop("MOCK_USERS_ENABLED", None)
            with (
                patch("backend.app._ensure_runtime_schema") as mock_schema,
                patch("backend.app.start_background_services") as mock_start,
            ):
                response = client.get("/")

            assert response.status_code == 401
            mock_schema.assert_not_called()
            mock_start.assert_not_called()
        finally:
            app.config["AUTH_PROXY_USERNAME_HEADER"] = original_header or ""
            if original_mock is not None:
                os.environ["MOCK_USERS_ENABLED"] = original_mock
            else:
                os.environ.pop("MOCK_USERS_ENABLED", None)


class TestIsAdmin:
    """Tests for is_admin function."""

    def test_admin_when_user_in_admin_list(self):
        """Test is_admin returns True when user is in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "John Doe"
            os.environ["ADMIN_USERS"] = "Admin,John Doe,Jane Smith"
            assert is_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_not_admin_when_user_not_in_list(self):
        """Test is_admin returns False when user is not in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin,John Doe"
            assert is_admin() is False
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_admin_with_whitespace_in_list(self):
        """Test is_admin handles whitespace around names in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "John Doe"
            os.environ["ADMIN_USERS"] = "Admin,  John Doe  , Jane Smith"
            assert is_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_admin_default_when_not_set(self):
        """Test is_admin with default Admin user when ADMIN_USERS not set."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Admin"
            if "ADMIN_USERS" in os.environ:
                del os.environ["ADMIN_USERS"]
            assert is_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins

    def test_not_admin_with_default_admin_users(self):
        """Test is_admin returns False for non-Admin when ADMIN_USERS defaults."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            if "ADMIN_USERS" in os.environ:
                del os.environ["ADMIN_USERS"]
            # Default ADMIN_USERS is "Admin", so "Regular User" should not be admin
            assert is_admin() is False
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins

    def test_admin_case_sensitive(self):
        """Test that admin matching is case-sensitive."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "admin"  # lowercase
            os.environ["ADMIN_USERS"] = "Admin"  # capitalized
            assert is_admin() is False  # Should not match
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_admin_with_single_user(self):
        """Test is_admin with single user in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Solo Admin"
            os.environ["ADMIN_USERS"] = "Solo Admin"
            assert is_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)


class TestIsPayrollAdmin:
    """Tests for is_payroll_admin function."""

    def test_true_when_user_in_payroll_admin_list(self):
        """Test is_payroll_admin returns True when user is in PAYROLL_ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Payroll User"
            os.environ["PAYROLL_ADMIN_USERS"] = "Payroll User,Another"
            assert is_payroll_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)

    def test_false_when_user_not_in_payroll_admin_list(self):
        """Test is_payroll_admin returns False when user is not listed."""
        original_user = os.environ.get("USER_NAME")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular Admin"
            os.environ["PAYROLL_ADMIN_USERS"] = "Payroll User"
            assert is_payroll_admin() is False
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)

    def test_false_when_env_var_not_set(self):
        """Test is_payroll_admin returns False when PAYROLL_ADMIN_USERS is unset."""
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            if "PAYROLL_ADMIN_USERS" in os.environ:
                del os.environ["PAYROLL_ADMIN_USERS"]
            assert is_payroll_admin() is False
        finally:
            if original_pa:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa

    def test_handles_whitespace_around_names(self):
        """Test is_payroll_admin strips whitespace from list entries."""
        original_user = os.environ.get("USER_NAME")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Payroll User"
            os.environ["PAYROLL_ADMIN_USERS"] = "  Payroll User  , Another"
            assert is_payroll_admin() is True
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)


class TestReportFiltering:
    """Tests for resident-filter report permissions."""

    def test_allows_listed_report_viewer(self, app):
        """Users in REPORT_VIEW_ALL_USERS can pick any resident in reports."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        original_viewers = os.environ.get("REPORT_VIEW_ALL_USERS")
        try:
            os.environ["USER_NAME"] = "Demo Viewer"
            os.environ["ADMIN_USERS"] = "Razvan Azamfirei"
            os.environ["PAYROLL_ADMIN_USERS"] = ""
            os.environ["REPORT_VIEW_ALL_USERS"] = "Demo Viewer"
            with app.test_request_context("/reports"):
                assert can_filter_reports_by_resident() is True
                assert is_admin() is False
                assert is_payroll_admin() is False
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)
            if original_viewers is not None:
                os.environ["REPORT_VIEW_ALL_USERS"] = original_viewers
            else:
                os.environ.pop("REPORT_VIEW_ALL_USERS", None)

    def test_denies_unlisted_report_viewer(self, app):
        """Users outside REPORT_VIEW_ALL_USERS remain self-only in reports."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        original_viewers = os.environ.get("REPORT_VIEW_ALL_USERS")
        try:
            os.environ["USER_NAME"] = "Regular Viewer"
            os.environ["ADMIN_USERS"] = "Razvan Azamfirei"
            os.environ["PAYROLL_ADMIN_USERS"] = ""
            os.environ["REPORT_VIEW_ALL_USERS"] = "Demo Viewer"
            with app.test_request_context("/reports"):
                assert can_filter_reports_by_resident() is False
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)
            if original_pa is not None:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            else:
                os.environ.pop("PAYROLL_ADMIN_USERS", None)
            if original_viewers is not None:
                os.environ["REPORT_VIEW_ALL_USERS"] = original_viewers
            else:
                os.environ.pop("REPORT_VIEW_ALL_USERS", None)


class TestIsFirstCall:
    """Tests for is_first_call function."""

    def test_false_when_no_resident_matches_user(self, app):
        """Return False when USER_NAME has no matching resident."""
        with app.app_context():
            original = os.environ.get("USER_NAME")
            try:
                os.environ["USER_NAME"] = "Nonexistent Person 99999"
                assert is_first_call(get_effective_date()) is False
            finally:
                if original is not None:
                    os.environ["USER_NAME"] = original
                else:
                    os.environ.pop("USER_NAME", None)

    def test_true_when_resident_has_first_call_entry(self, app):
        """Return True when the current user has a
        FIRST_CALL_ROLES entry for the date."""
        from backend.models import Resident, Role, TimeEntry, db

        with app.app_context():
            # Create a resident matching the user name
            resident = Resident(name="FC Test User", active=True)
            role = Role.query.filter_by(name="First Call").first()
            if role is None:
                role = Role(
                    name="First Call",
                    cutoff_hour=17,
                    cutoff_minute=30,
                    is_call_team=True,
                )
                db.session.add(role)

            db.session.add(resident)
            db.session.commit()

            today = get_effective_date()
            entry = TimeEntry(
                date=today,
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()

            original_user = os.environ.get("USER_NAME")
            try:
                os.environ["USER_NAME"] = "FC Test User"
                assert is_first_call(today) is True
            finally:
                if original_user is not None:
                    os.environ["USER_NAME"] = original_user
                else:
                    os.environ.pop("USER_NAME", None)
                db.session.delete(entry)
                db.session.delete(resident)
                db.session.commit()

    def test_false_when_resident_has_no_first_call_entry(self, app):
        """Return False when resident exists but not assigned a first-call role."""
        import os

        from backend.models import Resident, db

        with app.app_context():
            resident = Resident(name="Non FC User", active=True)
            db.session.add(resident)
            db.session.commit()

            original = os.environ.get("USER_NAME")
            try:
                os.environ["USER_NAME"] = "Non FC User"
                assert is_first_call(get_effective_date()) is False
            finally:
                if original is not None:
                    os.environ["USER_NAME"] = original
                else:
                    os.environ.pop("USER_NAME", None)
                db.session.delete(resident)
                db.session.commit()


class TestAdminRequiredDecorator:
    """Tests for admin_required decorator."""

    def test_admin_can_access_protected_route(self, client):
        """Test that admin users can access admin-protected routes."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Test Admin"
            os.environ["ADMIN_USERS"] = "Test Admin"

            response = client.get("/roles/")
            assert response.status_code == 200
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_non_admin_redirected_from_protected_route(self, client):
        """Test that non-admin users are redirected from admin-protected routes."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/roles/")
            assert response.status_code == 302  # Redirect

            # Follow redirect and check message
            response = client.get("/roles/", follow_redirects=True)
            assert b"Admin privileges required" in response.data
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_admin_required_redirects_to_index(self, client):
        """Test that admin_required redirects to sheets.index."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/roles/")
            assert response.status_code == 302
            # Should redirect to index (root)
            assert response.location in {"/", "http://localhost/"}
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_residents_route_requires_admin(self, client):
        """Test that residents route requires admin privileges."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/residents/")
            assert response.status_code == 302
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_audit_route_requires_admin(self, client):
        """Test that audit route requires admin privileges."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/audit")
            assert response.status_code == 302
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)
