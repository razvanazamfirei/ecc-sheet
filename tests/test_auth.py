"""Tests for authentication and authorization module."""

import os
from datetime import date, time

from backend.auth import get_current_user, is_admin, is_first_call, is_payroll_admin


class TestGetCurrentUser:
    """Tests for get_current_user function."""

    def test_returns_user_name_from_env(self):
        """Test that get_current_user returns USER_NAME from environment."""
        original = os.environ.get("USER_NAME")
        try:
            os.environ["USER_NAME"] = "Test User Name"
            assert get_current_user() == "Test User Name"
        finally:
            if original:
                os.environ["USER_NAME"] = original
            elif "USER_NAME" in os.environ:
                del os.environ["USER_NAME"]

    def test_returns_admin_when_not_set(self):
        """Test that get_current_user returns Admin when USER_NAME not set."""
        original = os.environ.get("USER_NAME")
        try:
            if "USER_NAME" in os.environ:
                del os.environ["USER_NAME"]
            assert get_current_user() == "Admin"
        finally:
            if original:
                os.environ["USER_NAME"] = original

    def test_returns_empty_string_if_set_empty(self):
        """Test that get_current_user returns empty string if USER_NAME is empty."""
        original = os.environ.get("USER_NAME")
        try:
            os.environ["USER_NAME"] = ""
            assert not get_current_user()
        finally:
            if original:
                os.environ["USER_NAME"] = original
            elif "USER_NAME" in os.environ:
                del os.environ["USER_NAME"]


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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_not_admin_when_user_not_in_list(self):
        """Test is_admin returns False when user is not in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin,John Doe"
            assert is_admin() is False
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_admin_with_whitespace_in_list(self):
        """Test is_admin handles whitespace around names in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "John Doe"
            os.environ["ADMIN_USERS"] = "Admin,  John Doe  , Jane Smith"
            assert is_admin() is True
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_admin_with_single_user(self):
        """Test is_admin with single user in ADMIN_USERS."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Solo Admin"
            os.environ["ADMIN_USERS"] = "Solo Admin"
            assert is_admin() is True
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins


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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_pa:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            elif "PAYROLL_ADMIN_USERS" in os.environ:
                del os.environ["PAYROLL_ADMIN_USERS"]

    def test_false_when_user_not_in_payroll_admin_list(self):
        """Test is_payroll_admin returns False when user is not listed."""
        original_user = os.environ.get("USER_NAME")
        original_pa = os.environ.get("PAYROLL_ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular Admin"
            os.environ["PAYROLL_ADMIN_USERS"] = "Payroll User"
            assert is_payroll_admin() is False
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_pa:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            elif "PAYROLL_ADMIN_USERS" in os.environ:
                del os.environ["PAYROLL_ADMIN_USERS"]

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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_pa:
                os.environ["PAYROLL_ADMIN_USERS"] = original_pa
            elif "PAYROLL_ADMIN_USERS" in os.environ:
                del os.environ["PAYROLL_ADMIN_USERS"]


class TestIsFirstCall:
    """Tests for is_first_call function."""

    def test_false_when_no_resident_matches_user(self, app):
        """Return False when USER_NAME has no matching resident."""
        with app.app_context():
            original = os.environ.get("USER_NAME")
            try:
                os.environ["USER_NAME"] = "Nonexistent Person 99999"
                assert is_first_call(date.today()) is False
            finally:
                if original:
                    os.environ["USER_NAME"] = original

    def test_true_when_resident_has_first_call_entry(self, app):
        """Return True when the current user has a FIRST_CALL_ROLES entry for the date."""
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

            today = date.today()
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
                if original_user:
                    os.environ["USER_NAME"] = original_user
                db.session.delete(entry)
                db.session.delete(resident)
                db.session.commit()

    def test_false_when_resident_has_no_first_call_entry(self, app):
        """Return False when resident exists but not assigned a first-call role."""
        import os
        from datetime import date

        from backend.models import Resident, db

        with app.app_context():
            resident = Resident(name="Non FC User", active=True)
            db.session.add(resident)
            db.session.commit()

            original = os.environ.get("USER_NAME")
            try:
                os.environ["USER_NAME"] = "Non FC User"
                assert is_first_call(date.today()) is False
            finally:
                if original:
                    os.environ["USER_NAME"] = original
                db.session.delete(resident)
                db.session.commit()


class TestAdminRequiredDecorator:
    """Tests for admin_required decorator."""

    def test_admin_can_access_protected_route(self, client, app):
        """Test that admin users can access admin-protected routes."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Test Admin"
            os.environ["ADMIN_USERS"] = "Test Admin"

            response = client.get("/roles/")
            assert response.status_code == 200
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_non_admin_redirected_from_protected_route(self, client, app):
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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_admin_required_redirects_to_index(self, client, app):
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
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_residents_route_requires_admin(self, client, app):
        """Test that residents route requires admin privileges."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/residents/")
            assert response.status_code == 302
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_audit_route_requires_admin(self, client, app):
        """Test that audit route requires admin privileges."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/audit")
            assert response.status_code == 302
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins
