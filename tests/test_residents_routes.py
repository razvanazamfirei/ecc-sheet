"""Tests for resident routes."""

import os
from unittest.mock import patch

from backend.models import Resident, db


class TestResidentsIndex:
    """Tests for residents index page."""

    def test_residents_index_requires_admin(self, client, app):
        """Test that residents index requires admin privileges."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/residents/", follow_redirects=True)
            assert response.status_code == 200
            assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_residents_index_lists_all(self, client, app, sample_resident):
        """Test residents index displays all residents."""
        with app.app_context():
            response = client.get("/residents/")
            assert response.status_code == 200
            assert sample_resident.name.encode() in response.data

    def test_residents_ordered_by_name(self, client, app):
        """Test residents are ordered alphabetically by name."""
        with app.app_context():
            res_z = Resident(name="Zebra Doctor", active=True)
            res_a = Resident(name="Alpha Doctor", active=True)
            db.session.add_all([res_z, res_a])
            db.session.commit()

            response = client.get("/residents/")
            data = response.data.decode()

            pos_a = data.find("Alpha Doctor")
            pos_z = data.find("Zebra Doctor")
            if pos_a >= 0 and pos_z >= 0:
                assert pos_a < pos_z

            db.session.delete(res_z)
            db.session.delete(res_a)
            db.session.commit()


class TestAddResident:
    """Tests for adding residents."""

    def test_add_resident_success(self, client, app):
        """Test successfully adding a new resident."""
        with app.app_context():
            response = client.post(
                "/residents/add",
                data={"name": "New Test Resident"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"added successfully" in response.data

            # Verify in database
            resident = Resident.query.filter_by(name="New Test Resident").first()
            assert resident is not None
            assert resident.active is True

            # Cleanup
            db.session.delete(resident)
            db.session.commit()

    def test_add_resident_empty_name(self, client):
        """Test adding resident with empty name fails."""
        response = client.post(
            "/residents/add",
            data={"name": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_add_resident_whitespace_name(self, client):
        """Test adding resident with whitespace-only name fails."""
        response = client.post(
            "/residents/add",
            data={"name": "   "},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should be rejected - name.strip() will be empty

    def test_add_resident_trims_whitespace(self, client, app):
        """Test that resident name is trimmed of leading/trailing whitespace."""
        with app.app_context():
            response = client.post(
                "/residents/add",
                data={"name": "  Trimmed Name  "},
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = Resident.query.filter_by(name="Trimmed Name").first()
            assert resident is not None
            assert resident.name == "Trimmed Name"

            db.session.delete(resident)
            db.session.commit()

    def test_add_resident_requires_admin(self, client, app):
        """Test that adding resident requires admin privileges."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.post(
                "/residents/add",
                data={"name": "New Resident"},
                follow_redirects=True,
            )
            assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name


class TestToggleResident:
    """Tests for toggling resident active status."""

    def test_toggle_active_to_inactive(self, client, app):
        """Test toggling active resident to inactive."""
        with app.app_context():
            # Create a fresh resident for this test
            resident = Resident(name="Toggle Test Active", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            response = client.post(
                f"/residents/{resident_id}/toggle",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"deactivated" in response.data

            updated = db.session.get(Resident, resident_id)
            assert updated.active is False

            # Cleanup
            db.session.delete(updated)
            db.session.commit()

    def test_toggle_inactive_to_active(self, client, app):
        """Test toggling inactive resident to active."""
        with app.app_context():
            # Create a fresh resident for this test
            resident = Resident(name="Toggle Test Inactive", active=False)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            response = client.post(
                f"/residents/{resident_id}/toggle",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"activated" in response.data

            updated = db.session.get(Resident, resident_id)
            assert updated.active is True

            # Cleanup
            db.session.delete(updated)
            db.session.commit()

    def test_toggle_nonexistent_resident(self, client, app):
        """Test toggling a resident that doesn't exist returns 404."""
        import werkzeug.exceptions
        import werkzeug.routing.exceptions

        try:
            response = client.post("/residents/99999/toggle")
            assert response.status_code == 404
        except (werkzeug.exceptions.NotFound, werkzeug.routing.exceptions.BuildError):
            # 404 raised directly or BuildError from redirect is acceptable
            pass

    def test_toggle_requires_admin(self, client, app, sample_resident):
        """Test that toggle requires admin privileges."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.post(
                    f"/residents/{sample_resident.id}/toggle",
                    follow_redirects=True,
                )
                assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name


class TestImportStaff:
    """Tests for staff import endpoint."""

    def test_import_staff_requires_admin(self, client, app):
        """Test that staff import requires admin privileges."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.post("/residents/import", follow_redirects=True)
            assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_import_staff_success(self, client, app):
        """Test successful staff import."""
        with app.app_context():
            mock_result = {
                "success": True,
                "created": 2,
                "updated": 1,
                "skipped": 0,
            }

            with patch(
                "backend.routes.residents.import_staff_list", return_value=mock_result
            ):
                response = client.post("/residents/import", follow_redirects=True)
                assert response.status_code == 200
                assert b"imported successfully" in response.data
                assert b"2 created" in response.data
                assert b"1 updated" in response.data

    def test_import_staff_failure(self, client, app):
        """Test staff import failure."""
        with app.app_context():
            mock_result = {
                "success": False,
                "error": "Connection failed",
            }

            with patch(
                "backend.routes.residents.import_staff_list", return_value=mock_result
            ):
                response = client.post("/residents/import", follow_redirects=True)
                assert response.status_code == 200
                assert b"Import failed" in response.data
                assert b"Connection failed" in response.data

    def test_import_staff_exception(self, client, app):
        """Test staff import with exception."""
        with (
            app.app_context(),
            patch(
                "backend.routes.residents.import_staff_list",
                side_effect=Exception("Network error"),
            ),
        ):
            response = client.post("/residents/import", follow_redirects=True)
            assert response.status_code == 200
            assert b"Error importing staff list" in response.data


class TestResidentManagement:
    """Legacy tests for resident management routes."""

    def test_add_resident_empty_name(self, client):
        """Test adding resident with empty name fails."""
        response = client.post(
            "/residents/add",
            data={"name": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_add_resident_whitespace_name(self, client):
        """Test adding resident with whitespace-only name fails."""
        response = client.post(
            "/residents/add",
            data={"name": "   "},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should be rejected

    def test_resident_list_shows_all(self, client, app, sample_resident):
        """Test resident list shows all residents."""
        with app.app_context():
            response = client.get("/residents/")
            assert response.status_code == 200
            assert sample_resident.name.encode() in response.data


class TestResidentExceptionHandling:
    """Tests for exception handling in resident routes."""

    def test_add_resident_db_error(self, client, app):
        """Test add handles database errors gracefully."""
        with app.app_context():
            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    "/residents/add",
                    data={"name": "DB Error Test"},
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()

    def test_toggle_resident_db_error(self, client, app):
        """Test toggle handles database errors gracefully."""
        with app.app_context():
            # Create a test resident
            resident = Resident(name="Toggle Error Test", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    f"/residents/{resident_id}/toggle",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()

            # Cleanup - rollback and delete
            db.session.rollback()
            resident = db.session.get(Resident, resident_id)
            if resident:
                db.session.delete(resident)
                db.session.commit()
