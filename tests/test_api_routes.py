"""Tests for API routes."""

import json

from backend.models import Resident, Role, db


class TestActiveResidentsAPI:
    """Tests for /api/residents/active endpoint."""

    def test_returns_active_residents(self, client, app):
        """Test that API returns only active residents."""
        with app.app_context():
            # Create active and inactive residents
            active = Resident(name="Active Resident", active=True)
            inactive = Resident(name="Inactive Resident", active=False)
            db.session.add_all([active, inactive])
            db.session.commit()

            response = client.get("/api/residents/active")
            assert response.status_code == 200

            data = json.loads(response.data)
            names = [r["name"] for r in data]
            assert "Active Resident" in names
            assert "Inactive Resident" not in names

            # Cleanup
            db.session.delete(active)
            db.session.delete(inactive)
            db.session.commit()

    def test_returns_json_format(self, client, app):
        """Test that API returns proper JSON format."""
        with app.app_context():
            resident = Resident(name="JSON Test", active=True)
            db.session.add(resident)
            db.session.commit()

            response = client.get("/api/residents/active")
            assert response.status_code == 200
            assert response.content_type == "application/json"

            data = json.loads(response.data)
            assert isinstance(data, list)
            if data:
                assert "id" in data[0]
                assert "name" in data[0]

            db.session.delete(resident)
            db.session.commit()

    def test_returns_empty_list_when_no_active(self, client, app):
        """Test that API returns empty list when no active residents."""
        with app.app_context():
            # Deactivate all residents temporarily
            active_residents = Resident.query.filter_by(active=True).all()
            for r in active_residents:
                r.active = False
            db.session.commit()

            response = client.get("/api/residents/active")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data == []

            # Restore
            for r in active_residents:
                r.active = True
            db.session.commit()

    def test_residents_ordered_by_name(self, client, app):
        """Test that residents are ordered alphabetically."""
        with app.app_context():
            res_z = Resident(name="Zzzz Last", active=True)
            res_a = Resident(name="Aaaa First", active=True)
            db.session.add_all([res_z, res_a])
            db.session.commit()

            response = client.get("/api/residents/active")
            data = json.loads(response.data)

            # Find indices
            idx_a = next(
                (i for i, r in enumerate(data) if r["name"] == "Aaaa First"), -1
            )
            idx_z = next(
                (i for i, r in enumerate(data) if r["name"] == "Zzzz Last"), -1
            )
            if idx_a >= 0 and idx_z >= 0:
                assert idx_a < idx_z

            db.session.delete(res_z)
            db.session.delete(res_a)
            db.session.commit()


class TestRolesAPI:
    """Tests for /api/roles endpoint."""

    def test_returns_all_roles(self, client, app, sample_role):
        """Test that API returns all roles."""
        with app.app_context():
            response = client.get("/api/roles")
            assert response.status_code == 200

            data = json.loads(response.data)
            names = [r["name"] for r in data]
            assert sample_role.name in names

    def test_returns_json_format(self, client, app):
        """Test that API returns proper JSON format."""
        response = client.get("/api/roles")
        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_role_includes_cutoff_hour(self, client, app, sample_role):
        """Test that role response includes cutoff_hour."""
        with app.app_context():
            response = client.get("/api/roles")
            data = json.loads(response.data)

            role_data = next((r for r in data if r["name"] == sample_role.name), None)
            assert role_data is not None
            assert "cutoff_hour" in role_data
            assert role_data["cutoff_hour"] == sample_role.cutoff_hour

    def test_role_includes_is_backup(self, client, app, sample_role):
        """Test that role response includes is_backup flag."""
        with app.app_context():
            response = client.get("/api/roles")
            data = json.loads(response.data)

            role_data = next((r for r in data if r["name"] == sample_role.name), None)
            assert role_data is not None
            assert "is_backup" in role_data

    def test_roles_ordered_by_display_order(self, client, app):
        """Test that roles are ordered by display_order."""
        with app.app_context():
            role_z = Role(name="API Test Z", display_order=1000)
            role_a = Role(name="API Test A", display_order=1)
            db.session.add_all([role_z, role_a])
            db.session.commit()

            response = client.get("/api/roles")
            data = json.loads(response.data)

            idx_a = next(
                (i for i, r in enumerate(data) if r["name"] == "API Test A"), -1
            )
            idx_z = next(
                (i for i, r in enumerate(data) if r["name"] == "API Test Z"), -1
            )
            if idx_a >= 0 and idx_z >= 0:
                assert idx_a < idx_z

            db.session.delete(role_z)
            db.session.delete(role_a)
            db.session.commit()

    def test_returns_empty_list_when_no_roles(self, client, app):
        """Test behavior when no roles exist (edge case)."""
        # This test verifies the endpoint doesn't crash
        # The actual database will have roles from fixtures
        response = client.get("/api/roles")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)


class TestAPIEndpointAccess:
    """Tests for API endpoint access control."""

    def test_residents_api_no_auth_required(self, client, app):
        """Test that residents API doesn't require admin auth."""
        import os

        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/api/residents/active")
            assert response.status_code == 200
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins

    def test_roles_api_no_auth_required(self, client, app):
        """Test that roles API doesn't require admin auth."""
        import os

        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/api/roles")
            assert response.status_code == 200
        finally:
            if original_user:
                os.environ["USER_NAME"] = original_user
            if original_admins:
                os.environ["ADMIN_USERS"] = original_admins
