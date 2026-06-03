"""Tests for authentication and authorization module."""

from datetime import time
from unittest.mock import patch

import pytest

from backend.auth import (
    can_filter_reports_by_resident,
    get_current_resident_id,
    get_current_user,
    is_admin,
    is_first_call,
    is_payroll_admin,
)
from backend.models import Resident, db
from backend.utils import get_effective_date


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    def test_returns_user_name_from_env(self, monkeypatch):
        """Test that get_current_user returns USER_NAME from environment."""
        monkeypatch.setenv("USER_NAME", "Test User Name")
        assert get_current_user() == "Test User Name"

    def test_returns_admin_when_not_set(self, monkeypatch):
        """Test that get_current_user returns Admin when USER_NAME not set."""
        monkeypatch.delenv("USER_NAME", raising=False)
        assert get_current_user() == "Admin"

    def test_returns_empty_string_if_set_empty(self, monkeypatch):
        """Test that get_current_user returns empty string if USER_NAME is empty."""
        monkeypatch.setenv("USER_NAME", "")
        assert not get_current_user()

    def test_uses_proxy_header_when_configured(self, app, monkeypatch):
        """Test proxy-auth header overrides USER_NAME inside a request context."""
        monkeypatch.setenv("USER_NAME", "Env User")
        monkeypatch.setitem(app.config, "AUTH_PROXY_USERNAME_HEADER", "X-Auth-User")
        with app.test_request_context("/", headers={"X-Auth-User": "Proxy User"}):
            assert get_current_user() == "Proxy User"

    @pytest.mark.usefixtures("saml_enabled_app")
    def test_uses_session_authenticated_user_when_present(self, client):
        """Test SAML/session auth overrides USER_NAME inside requests."""
        with client.session_transaction() as sess:
            sess["auth_user"] = "Session User"

        response = client.get("/")

        assert response.status_code == 200
        assert b"Session User" in response.data

    def test_proxy_header_returns_empty_user_when_missing(self, app, monkeypatch):
        """Test proxy-auth configuration fails closed when the header is absent."""
        monkeypatch.setenv("USER_NAME", "Env User")
        monkeypatch.setitem(app.config, "AUTH_PROXY_USERNAME_HEADER", "X-Auth-User")
        with app.test_request_context("/"):
            assert not get_current_user()

    def test_proxy_auth_rejects_request_without_header(self, client, app, monkeypatch):
        """Requests are rejected when proxy-auth is configured without a user."""
        monkeypatch.setitem(app.config, "AUTH_PROXY_USERNAME_HEADER", "X-Auth-User")
        monkeypatch.delenv("MOCK_USERS_ENABLED", raising=False)
        response = client.get("/")
        assert response.status_code == 401
        assert b"Authentication required" in response.data

    def test_proxy_auth_401_skips_schema_and_background_bootstrap(
        self, client, app, monkeypatch
    ):
        """Unauthorized proxy-auth requests should not trigger bootstrap work."""
        monkeypatch.setitem(app.config, "AUTH_PROXY_USERNAME_HEADER", "X-Auth-User")
        monkeypatch.delenv("MOCK_USERS_ENABLED", raising=False)
        with (
            patch("backend.app._ensure_runtime_schema") as mock_schema,
            patch("backend.app.start_background_services") as mock_start,
        ):
            response = client.get("/")

        assert response.status_code == 401
        mock_schema.assert_not_called()
        mock_start.assert_not_called()


class TestIsAdmin:
    """Tests for is_admin function."""

    def test_admin_when_user_in_admin_list(self, monkeypatch):
        """Test is_admin returns True when user is in ADMIN_USERS."""
        monkeypatch.setenv("USER_NAME", "John Doe")
        monkeypatch.setenv("ADMIN_USERS", "Admin,John Doe,Jane Smith")
        assert is_admin() is True

    def test_not_admin_when_user_not_in_list(self, monkeypatch):
        """Test is_admin returns False when user is not in ADMIN_USERS."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin,John Doe")
        assert is_admin() is False

    def test_admin_with_whitespace_in_list(self, monkeypatch):
        """Test is_admin handles whitespace around names in ADMIN_USERS."""
        monkeypatch.setenv("USER_NAME", "John Doe")
        monkeypatch.setenv("ADMIN_USERS", "Admin,  John Doe  , Jane Smith")
        assert is_admin() is True

    def test_admin_default_when_not_set(self, monkeypatch):
        """Test is_admin with default Admin user when ADMIN_USERS not set."""
        monkeypatch.setenv("USER_NAME", "Admin")
        monkeypatch.delenv("ADMIN_USERS", raising=False)
        assert is_admin() is True

    def test_not_admin_with_default_admin_users(self, monkeypatch):
        """Test is_admin returns False for non-Admin when ADMIN_USERS defaults."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.delenv("ADMIN_USERS", raising=False)
        assert is_admin() is False


class TestGetCurrentResidentId:
    def test_matches_by_abbreviation_first(self, app):
        with app.app_context():
            resident = Resident(
                name="Razvan Azamfirei",
                abbreviation="AzamfirR",
                email="azamfirr@pennmedicine.upenn.edu",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            try:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    monkeypatch.setattr(
                        "backend.auth.get_current_user", lambda: "AzamfirR"
                    )
                    assert get_current_resident_id() == resident.id
            finally:
                db.session.delete(resident)
                db.session.commit()

    def test_falls_back_to_email_when_abbreviation_missing(self, app):
        with app.app_context():
            resident = Resident(
                name="Razvan Azamfirei",
                abbreviation=None,
                email="azamfirr@pennmedicine.upenn.edu",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            try:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    monkeypatch.setattr(
                        "backend.auth.get_current_user",
                        lambda: "azamfirr@pennmedicine.upenn.edu",
                    )
                    assert get_current_resident_id() == resident.id
            finally:
                db.session.delete(resident)
                db.session.commit()

    def test_falls_back_to_name_when_abbreviation_and_email_do_not_match(self, app):
        with app.app_context():
            resident = Resident(
                name="Razvan Azamfirei",
                abbreviation=None,
                email="not-the-current-user@pennmedicine.upenn.edu",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            try:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    monkeypatch.setattr(
                        "backend.auth.get_current_user",
                        lambda: "not-the-current-user@pennmedicine.upenn.edu",
                    )
                    assert get_current_resident_id() == resident.id
            finally:
                db.session.delete(resident)
                db.session.commit()

    def test_returns_none_when_user_is_empty(self, app):
        """Test get_current_resident_id returns None when user is empty/whitespace."""
        with app.app_context(), pytest.MonkeyPatch.context() as monkeypatch:
            # Monkeypatch get_current_user to an empty string
            monkeypatch.setattr("backend.auth.get_current_user", lambda: "")
            assert get_current_resident_id() is None

            # Monkeypatch get_current_user to whitespace
            monkeypatch.setattr("backend.auth.get_current_user", lambda: "   ")
            assert get_current_resident_id() is None

    def test_returns_none_when_no_match(self, app):
        """Test get_current_resident_id returns None when no resident matches user."""
        with app.app_context():
            # Create a resident that does NOT match the current user
            resident = Resident(
                name="Non Match User",
                abbreviation="NoMatch",
                email="nomatch@pennmedicine.upenn.edu",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            try:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    # Monkeypatch get_current_user to a value that matches NOTHING
                    monkeypatch.setattr(
                        "backend.auth.get_current_user",
                        lambda: "Different Person entirely",
                    )
                    assert get_current_resident_id() is None
            finally:
                db.session.delete(resident)
                db.session.commit()

    def test_admin_case_sensitive(self, monkeypatch):
        """Test that admin matching is case-sensitive."""
        monkeypatch.setenv("USER_NAME", "admin")
        monkeypatch.setenv("ADMIN_USERS", "Admin")
        assert is_admin() is False

    def test_admin_with_single_user(self, monkeypatch):
        """Test is_admin with single user in ADMIN_USERS."""
        monkeypatch.setenv("USER_NAME", "Solo Admin")
        monkeypatch.setenv("ADMIN_USERS", "Solo Admin")
        assert is_admin() is True


class TestIsPayrollAdmin:
    """Tests for is_payroll_admin function."""

    def test_true_when_user_in_payroll_admin_list(self, monkeypatch):
        """Test is_payroll_admin returns True when user is in PAYROLL_ADMIN_USERS."""
        monkeypatch.setenv("USER_NAME", "Payroll User")
        monkeypatch.setenv("PAYROLL_ADMIN_USERS", "Payroll User,Another")
        assert is_payroll_admin() is True

    def test_false_when_user_not_in_payroll_admin_list(self, monkeypatch):
        """Test is_payroll_admin returns False when user is not listed."""
        monkeypatch.setenv("USER_NAME", "Regular Admin")
        monkeypatch.setenv("PAYROLL_ADMIN_USERS", "Payroll User")
        assert is_payroll_admin() is False

    def test_false_when_env_var_not_set(self, monkeypatch):
        """Test is_payroll_admin returns False when PAYROLL_ADMIN_USERS is unset."""
        monkeypatch.delenv("PAYROLL_ADMIN_USERS", raising=False)
        assert is_payroll_admin() is False

    def test_handles_whitespace_around_names(self, monkeypatch):
        """Test is_payroll_admin strips whitespace from list entries."""
        monkeypatch.setenv("USER_NAME", "Payroll User")
        monkeypatch.setenv("PAYROLL_ADMIN_USERS", "  Payroll User  , Another")
        assert is_payroll_admin() is True


class TestReportFiltering:
    """Tests for resident-filter report permissions."""

    def test_allows_listed_report_viewer(self, app, monkeypatch):
        """Users in REPORT_VIEW_ALL_USERS can pick any resident in reports."""
        monkeypatch.setenv("USER_NAME", "Demo Viewer")
        monkeypatch.setenv("ADMIN_USERS", "Razvan Azamfirei")
        monkeypatch.setenv("PAYROLL_ADMIN_USERS", "")
        monkeypatch.setenv("REPORT_VIEW_ALL_USERS", "Demo Viewer")
        with app.test_request_context("/reports"):
            assert can_filter_reports_by_resident() is True
            assert is_admin() is False
            assert is_payroll_admin() is False

    def test_denies_unlisted_report_viewer(self, app, monkeypatch):
        """Users outside REPORT_VIEW_ALL_USERS remain self-only in reports."""
        monkeypatch.setenv("USER_NAME", "Regular Viewer")
        monkeypatch.setenv("ADMIN_USERS", "Razvan Azamfirei")
        monkeypatch.setenv("PAYROLL_ADMIN_USERS", "")
        monkeypatch.setenv("REPORT_VIEW_ALL_USERS", "Demo Viewer")
        with app.test_request_context("/reports"):
            assert can_filter_reports_by_resident() is False


class TestIsFirstCall:
    """Tests for is_first_call function."""

    def test_false_when_no_resident_matches_user(self, app, monkeypatch):
        """Return False when USER_NAME has no matching resident."""
        with app.app_context():
            monkeypatch.setenv("USER_NAME", "Nonexistent Person 99999")
            assert is_first_call(get_effective_date()) is False

    def test_true_when_resident_has_first_call_entry(self, app, monkeypatch):
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

            monkeypatch.setenv("USER_NAME", "FC Test User")
            try:
                assert is_first_call(today) is True
            finally:
                db.session.delete(entry)
                db.session.delete(resident)
                db.session.commit()

    def test_false_when_resident_has_no_first_call_entry(self, app, monkeypatch):
        """Return False when resident exists but not assigned a first-call role."""
        from backend.models import Resident, db

        with app.app_context():
            resident = Resident(name="Non FC User", active=True)
            db.session.add(resident)
            db.session.commit()

            monkeypatch.setenv("USER_NAME", "Non FC User")
            try:
                assert is_first_call(get_effective_date()) is False
            finally:
                db.session.delete(resident)
                db.session.commit()


class TestAdminRequiredDecorator:
    """Tests for admin_required decorator."""

    def test_admin_can_access_protected_route(self, client, monkeypatch):
        """Test that admin users can access admin-protected routes."""
        monkeypatch.setenv("USER_NAME", "Test Admin")
        monkeypatch.setenv("ADMIN_USERS", "Test Admin")

        response = client.get("/roles/")
        assert response.status_code == 200

    def test_non_admin_redirected_from_protected_route(self, client, monkeypatch):
        """Test that non-admin users are redirected from admin-protected routes."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/roles/")
        assert response.status_code == 302

        response = client.get("/roles/", follow_redirects=True)
        assert b"Admin privileges required" in response.data

    def test_admin_required_redirects_to_index(self, client, monkeypatch):
        """Test that admin_required redirects to sheets.index."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/roles/")
        assert response.status_code == 302
        assert response.location in {"/", "http://localhost/"}

    def test_residents_route_requires_admin(self, client, monkeypatch):
        """Test that residents route requires admin privileges."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/residents/")
        assert response.status_code == 302

    def test_audit_route_requires_admin(self, client, monkeypatch):
        """Test that audit route requires admin privileges."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/audit")
        assert response.status_code == 302


class TestCanLogout:
    """Tests for can_logout template context variable."""

    def test_false_when_mock_disabled_and_no_saml(self, client, monkeypatch):
        """can_logout is False when mock users disabled and SAML is off."""
        monkeypatch.delenv("MOCK_USERS_ENABLED", raising=False)
        response = client.get("/")
        assert response.status_code == 200
        assert b"dev/sign-out" not in response.data
        assert b'href="/dev/sign-out"' not in response.data

    def test_true_when_mock_enabled_and_dev_user_in_session(self, client, monkeypatch):
        """can_logout is True when mock users enabled and dev_user is in session."""
        monkeypatch.setenv("MOCK_USERS_ENABLED", "true")
        with client.session_transaction() as sess:
            sess["dev_user"] = "Admin"
        response = client.get("/")
        assert response.status_code == 200
        assert b'action="/dev/sign-out"' in response.data
        assert b'href="/dev/sign-out"' not in response.data

    def test_false_when_mock_enabled_but_no_dev_user_in_session(
        self, client, monkeypatch
    ):
        """can_logout is False when mock users enabled but no dev_user set."""
        monkeypatch.setenv("MOCK_USERS_ENABLED", "true")
        with client.session_transaction() as sess:
            sess.pop("dev_user", None)
        response = client.get("/")
        assert response.status_code == 200
        assert b"/dev/sign-out" not in response.data


class TestDevRoutes:
    """Tests for /dev/* routes."""

    def test_sign_out_clears_dev_user_and_redirects(self, client, monkeypatch):
        """POST /dev/sign-out clears dev_user from session and redirects."""
        monkeypatch.setenv("MOCK_USERS_ENABLED", "true")
        with client.session_transaction() as sess:
            sess["dev_user"] = "Some User"
        response = client.post("/dev/sign-out")
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert "dev_user" not in sess

    def test_sign_out_returns_404_when_mock_disabled(self, client, monkeypatch):
        """POST /dev/sign-out returns 404 when MOCK_USERS_ENABLED is not set."""
        monkeypatch.delenv("MOCK_USERS_ENABLED", raising=False)
        response = client.post("/dev/sign-out")
        assert response.status_code == 404
