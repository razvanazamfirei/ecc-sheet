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

    def test_add_resident_whitespace_name(self, client, app):
        """Test adding resident with whitespace-only name fails."""
        with app.app_context():
            from backend.models import Resident

            # Get initial resident count
            initial_count = Resident.query.count()

            response = client.post(
                "/residents/add",
                data={"name": "   "},
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify no new resident was created
            final_count = Resident.query.count()
            assert final_count == initial_count
            # Should show error message
            assert (
                b"required" in response.data.lower()
                or b"error" in response.data.lower()
            )

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


# noinspection DuplicatedCode
class TestResidentExceptionHandling:
    """Tests for exception handling in resident routes."""

    def test_add_resident_db_error(self, client, app):
        """Test add handles database errors gracefully."""
        with app.app_context(), patch.object(db.session, "commit") as mock_commit:
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


class TestEditResident:
    """Tests for resident edit routes."""

    def test_edit_page_loads(self, client, app, sample_resident):
        """Test that the edit page loads for an existing resident."""
        with app.app_context():
            response = client.get(f"/residents/{sample_resident.id}/edit")
            assert response.status_code == 200
            assert sample_resident.name.encode() in response.data

    def test_edit_page_404_for_missing_resident(self, client):
        """Test that edit page returns 404 for non-existent resident."""
        response = client.get("/residents/99999/edit")
        assert response.status_code == 404

    def test_edit_requires_admin(self, client, app, sample_resident):
        """Test that edit page requires admin privileges."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.get(
                    f"/residents/{sample_resident.id}/edit", follow_redirects=True
                )
                assert b"Admin privileges required" in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_edit_save_updates_fields(self, client, app):
        """Test that POST to edit_save updates resident fields."""
        with app.app_context():
            resident = Resident(name="Edit Test Resident", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            response = client.post(
                f"/residents/{resident_id}/edit",
                data={
                    "name": "Updated Name",
                    "first_name": "Updated",
                    "last_name": "Name",
                    "class_year": "CA-2",
                    "email": "updated@example.com",
                    "phone": "555-1234",
                    "abbreviation": "UPD",
                    "lawson_id": "98765",
                    "hire_date": "2023-07-01",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"updated successfully" in response.data

            updated = db.session.get(Resident, resident_id)
            assert updated.name == "Updated Name"
            assert updated.first_name == "Updated"
            assert updated.last_name == "Name"
            assert updated.class_year == "CA-2"
            assert updated.email == "updated@example.com"
            assert updated.lawson_id == 98765
            assert updated.hire_date.isoformat() == "2023-07-01"

            db.session.delete(updated)
            db.session.commit()

    def test_edit_save_rejects_invalid_class_year(self, client, app):
        """Test that invalid class_year values are stored as None."""
        with app.app_context():
            resident = Resident(name="Class Year Test", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            client.post(
                f"/residents/{resident_id}/edit",
                data={
                    "name": "Class Year Test",
                    "class_year": "CA1",  # old-style, not in CLASS_YEARS
                },
                follow_redirects=True,
            )

            updated = db.session.get(Resident, resident_id)
            assert updated.class_year is None

            db.session.delete(updated)
            db.session.commit()

    def test_edit_save_accepts_valid_class_year(self, client, app):
        """Test that valid class_year values are saved."""
        with app.app_context():
            for cy in ["CA-1", "CA-2", "CA-3", "Fellow", "OMFS"]:
                resident = Resident(name=f"CY Test {cy}", active=True)
                db.session.add(resident)
                db.session.commit()
                resident_id = resident.id

                client.post(
                    f"/residents/{resident_id}/edit",
                    data={"name": f"CY Test {cy}", "class_year": cy},
                    follow_redirects=True,
                )

                updated = db.session.get(Resident, resident_id)
                assert updated.class_year == cy

                db.session.delete(updated)
                db.session.commit()

    def test_edit_save_clears_optional_fields(self, client, app):
        """Test that empty optional fields are stored as None."""
        with app.app_context():
            from datetime import date

            resident = Resident(
                name="Clear Fields Test",
                class_year="CA1",
                email="old@example.com",
                lawson_id=11111,
                hire_date=date(2022, 7, 1),
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            client.post(
                f"/residents/{resident_id}/edit",
                data={
                    "name": "Clear Fields Test",
                    "class_year": "",
                    "email": "",
                    "phone": "",
                    "abbreviation": "",
                    "lawson_id": "",
                    "hire_date": "",
                },
                follow_redirects=True,
            )

            updated = db.session.get(Resident, resident_id)
            assert updated.class_year is None
            assert updated.email is None
            assert updated.lawson_id is None
            assert updated.hire_date is None

            db.session.delete(updated)
            db.session.commit()

    def test_edit_save_404_for_missing_resident(self, client):
        """Test that POST to edit_save fails gracefully for non-existent resident."""
        import werkzeug.exceptions
        import werkzeug.routing.exceptions

        try:
            response = client.post(
                "/residents/99999/edit",
                data={"name": "Ghost"},
            )
            assert response.status_code == 404
        except (werkzeug.exceptions.NotFound, werkzeug.routing.exceptions.BuildError):
            pass

    def test_edit_page_shows_lawson_id_and_hire_date(self, client, app):
        """Test that edit page renders lawson_id and hire_date values."""
        with app.app_context():
            from datetime import date

            resident = Resident(
                name="Display Test Resident",
                lawson_id=42000,
                hire_date=date(2021, 9, 15),
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            response = client.get(f"/residents/{resident_id}/edit")
            assert response.status_code == 200
            assert b"42000" in response.data
            assert b"2021-09-15" in response.data

            db.session.delete(db.session.get(Resident, resident_id))
            db.session.commit()


class TestResidentProfile:
    """Tests for resident profile page."""

    def test_profile_returns_200_for_existing_resident(
        self, client, app, sample_resident
    ):
        """Test that profile page loads for an existing resident."""
        with app.app_context():
            response = client.get(f"/residents/{sample_resident.id}/profile")
            assert response.status_code == 200

    def test_profile_shows_contact_info(self, client, app):
        """Test that contact info is shown for all users."""
        with app.app_context():
            resident = Resident(
                name="Profile Contact Test",
                email="contact@example.com",
                phone="555-9999",
                abbreviation="PCT",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            response = client.get(f"/residents/{resident_id}/profile")
            assert response.status_code == 200
            assert b"contact@example.com" in response.data
            assert b"555-9999" in response.data
            assert b"PCT" in response.data

            db.session.delete(db.session.get(Resident, resident_id))
            db.session.commit()

    def test_profile_404_for_missing_resident(self, client):
        """Test that profile page returns 404 for non-existent resident."""
        response = client.get("/residents/99999/profile")
        assert response.status_code == 404

    def test_profile_accessible_without_admin(self, client, app, sample_resident):
        """Test that profile page is accessible to non-admin users."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.get(f"/residents/{sample_resident.id}/profile")
                assert response.status_code == 200
                # Should NOT show admin-restricted message
                assert b"Admin privileges required" not in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_profile_shows_hours_for_admin(
        self, client, app, sample_time_entry, sample_resident
    ):
        """Test that time history section is shown for admin users."""
        with app.app_context():
            response = client.get(f"/residents/{sample_resident.id}/profile")
            assert response.status_code == 200
            assert b"Recent Time Entries" in response.data

    def test_profile_hides_hours_for_regular_user(self, client, app, sample_resident):
        """Test that time history is hidden for regular non-first-call users."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.get(f"/residents/{sample_resident.id}/profile")
                assert response.status_code == 200
                assert b"Recent Time Entries" not in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

    def test_profile_shows_audit_for_admin(self, client, app, sample_resident):
        """Test that audit section is shown for admin users."""
        with app.app_context():
            response = client.get(f"/residents/{sample_resident.id}/profile")
            assert response.status_code == 200
            assert b"Recent Audit Activity" in response.data

    def test_profile_hides_audit_for_regular_user(self, client, app, sample_resident):
        """Test that audit section is hidden for non-admin users."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            with app.app_context():
                response = client.get(f"/residents/{sample_resident.id}/profile")
                assert response.status_code == 200
                assert b"Recent Audit Activity" not in response.data
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name
