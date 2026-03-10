"""Tests for role management routes."""

import json

from backend.models import AuditLog, Role, db


class TestRolesIndex:
    """Tests for the roles index page."""

    def test_roles_index_requires_admin(self, client):
        """Test that roles index requires admin privileges."""
        import os

        # Save current admin users
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            # Set up non-admin user
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/roles/", follow_redirects=True)
            assert response.status_code == 200
            assert b"Admin privileges required" in response.data
        finally:
            # Restore original values
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_roles_index_lists_all_roles(self, client, app, sample_role):
        """Test that roles index displays all roles."""
        with app.app_context():
            response = client.get("/roles/")
            assert response.status_code == 200
            assert sample_role.name.encode() in response.data

    def test_roles_index_shows_cutoff_times(self, client, app):
        """Test that roles index shows cutoff times."""
        with app.app_context():
            response = client.get("/roles/")
            assert response.status_code == 200
            # Check for cutoff hour display
            assert b"17" in response.data or b"5:" in response.data

    def test_roles_ordered_by_display_order(self, client, app):
        """Test that roles are ordered by display_order."""
        with app.app_context():
            # Create roles with specific display orders
            role1 = Role(name="Role Z", display_order=100)
            role2 = Role(name="Role A", display_order=1)
            db.session.add_all([role1, role2])
            db.session.commit()

            response = client.get("/roles/")
            assert response.status_code == 200

            # Role A (display_order=1) should appear before Role Z (display_order=100)
            data = response.data.decode()
            pos_a = data.find("Role A")
            pos_z = data.find("Role Z")
            if pos_a >= 0 and pos_z >= 0:
                assert pos_a < pos_z

            # Cleanup
            db.session.delete(role1)
            db.session.delete(role2)
            db.session.commit()


class TestRolesUpdate:
    """Tests for role update endpoint."""

    def test_update_role_cutoff_time(self, client, app, sample_role):
        """Test updating role cutoff time."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "18", "cutoff_minute": "45"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"updated successfully" in response.data

            # Verify the update
            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.cutoff_hour == 18
            assert updated_role.cutoff_minute == 45

    def test_update_role_with_backup_status(self, client, app, sample_role):
        """Test updating role backup status."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17", "cutoff_minute": "30", "is_backup": "on"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.is_backup is True

    def test_update_role_disable_backup(self, client, app, sample_role):
        """Test disabling backup status."""
        with app.app_context():
            # First enable backup
            sample_role.is_backup = True
            db.session.commit()

            # Then disable it
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17", "cutoff_minute": "30"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.is_backup is False

    def test_update_role_creates_audit_log(self, client, app, sample_role):
        """Test role updates are written to the audit log."""
        with app.app_context():
            role_id = sample_role.id
            response = client.post(
                f"/roles/{role_id}/update",
                data={"cutoff_hour": "18", "cutoff_minute": "15", "is_backup": "on"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            db.session.remove()
            log = (
                AuditLog.query.filter_by(
                    entity_type="Role", entity_id=role_id, action="UPDATE"
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None
            parsed = json.loads(log.details or "{}")
            assert parsed["changes"]["cutoff_hour"]["new"] == 18
            assert parsed["changes"]["is_backup"]["new"] is True

            db.session.delete(log)
            db.session.commit()

    def test_update_role_invalid_hour_too_high(self, client, app, sample_role):
        """Test updating role with invalid hour (>23) fails."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "24", "cutoff_minute": "30"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()

    def test_update_role_invalid_hour_negative(self, client, app, sample_role):
        """Test updating role with negative hour fails."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "-1", "cutoff_minute": "30"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()

    def test_update_role_invalid_minute_too_high(self, client, app, sample_role):
        """Test updating role with invalid minute (>59) fails."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17", "cutoff_minute": "60"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()

    def test_update_role_invalid_minute_negative(self, client, app, sample_role):
        """Test updating role with negative minute fails."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17", "cutoff_minute": "-1"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()

    def test_update_nonexistent_role(self, client):
        """Test updating a role that doesn't exist returns 404."""
        response = client.post(
            "/roles/99999/update",
            data={"cutoff_hour": "17", "cutoff_minute": "30"},
        )
        assert response.status_code == 404

    def test_update_role_defaults_when_missing_values(self, client, app, sample_role):
        """Test updating role uses defaults for missing values."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={},  # No data provided
                follow_redirects=True,
            )
            assert response.status_code == 200

            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.cutoff_hour == 17  # Default
            assert updated_role.cutoff_minute == 30  # Default

    def test_update_role_boundary_values(self, client, app, sample_role):
        """Test updating role with boundary valid values."""
        with app.app_context():
            # Test hour = 0
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "0", "cutoff_minute": "0"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.cutoff_hour == 0
            assert updated_role.cutoff_minute == 0

            # Test hour = 23, minute = 59
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "23", "cutoff_minute": "59"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            updated_role = db.session.get(Role, sample_role.id)
            assert updated_role is not None
            assert updated_role.cutoff_hour == 23
            assert updated_role.cutoff_minute == 59

    def test_update_role_requires_admin(self, client, app, sample_role):
        """Test that update requires admin privileges."""
        import os

        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.post(
                    f"/roles/{sample_role.id}/update",
                    data={"cutoff_hour": "18", "cutoff_minute": "45"},
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name


class TestRolesEdgeCases:
    """Edge case tests for roles routes."""

    def test_update_role_with_non_numeric_hour(self, client, app, sample_role):
        """Test updating role with non-numeric hour."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "abc", "cutoff_minute": "30"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()
            assert b"Cutoff hour and minute must be whole numbers." in response.data
            assert b"invalid literal" not in response.data

    def test_update_role_with_non_numeric_minute(self, client, app, sample_role):
        """Test updating role with non-numeric minute."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17", "cutoff_minute": "xyz"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"error" in response.data.lower()
            assert b"Cutoff hour and minute must be whole numbers." in response.data
            assert b"invalid literal" not in response.data

    def test_update_role_with_float_values(self, client, app, sample_role):
        """Test updating role with float values."""
        with app.app_context():
            response = client.post(
                f"/roles/{sample_role.id}/update",
                data={"cutoff_hour": "17.5", "cutoff_minute": "30.5"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should either truncate or error
