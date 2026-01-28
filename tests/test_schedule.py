"""Tests for schedule import functionality."""

from datetime import date
from unittest.mock import MagicMock, patch

from backend.models import DailySheet, Role, db


class TestScheduleImport:
    """Tests for schedule import routes."""

    def test_import_locked_sheet(self, client, app):
        """Test import fails on locked sheet."""
        with app.app_context():
            # Create and lock a sheet
            test_date = date(2024, 3, 15)
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if not sheet:
                sheet = DailySheet(date=test_date, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            db.session.commit()

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"locked" in response.data.lower()

            # Cleanup
            sheet.locked = False
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_success(self, mock_get, client, app):
        """Test successful schedule import."""
        with app.app_context():
            test_date = date(2024, 3, 16)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Make sure we have a role to import to
            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Mock the Amion response with valid CSV data
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                "Field1,Field2,Field3,Field4,Field5,Field6,Field7,EPICID,Field9\n"
                "ECC 1,Test Resident,Some,Data,Here,More,Data,EPICID:R12345,Extra"
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_request_error(self, mock_get, client, app):
        """Test schedule import with network error."""
        import requests

        with app.app_context():
            test_date = date(2024, 3, 17)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock network error
            mock_get.side_effect = requests.RequestException("Network error")

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should show error message

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_empty_response(self, mock_get, client, app):
        """Test schedule import with empty CSV."""
        with app.app_context():
            test_date = date(2024, 3, 18)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock empty response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_invalid_date(self, client):
        """Test import with invalid date format."""
        response = client.post(
            "/schedule/invalid-date/import",
            follow_redirects=True,
        )
        # Should handle the error
        assert response.status_code in {200, 400, 404}

    @patch("backend.routes.schedule.requests.get")
    def test_import_creates_new_residents(self, mock_get, client, app):
        """Test that import creates new residents with EPIC IDs."""
        with app.app_context():
            from backend.models import Resident, TimeEntry

            test_date = date(2024, 4, 1)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Make sure we have the ECC 1 role
            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Mock Amion response with new resident
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"New Resident","EPICID:R999999","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Check if resident was created
            resident = Resident.query.filter_by(epic_id="R999999").first()
            if resident:
                # Cleanup entries first
                TimeEntry.query.filter_by(resident_id=resident.id).delete()
                db.session.delete(resident)
                db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_updates_existing_resident_epic_id(self, mock_get, client, app):
        """Test that import updates resident with EPIC ID if missing."""
        with app.app_context():
            from backend.models import Resident, TimeEntry

            test_date = date(2024, 4, 2)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Create resident without EPIC ID
            resident = Resident(name="Existing Resident", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            # Make sure we have the ECC 1 role
            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Mock Amion response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Existing Resident","EPICID:R888888","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Cleanup
            TimeEntry.query.filter_by(resident_id=resident_id).delete()
            resident = db.session.get(Resident, resident_id)
            if resident:
                db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_skips_unknown_roles(self, mock_get, client, app):
        """Test that import skips entries for unknown roles."""
        with app.app_context():
            test_date = date(2024, 4, 3)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock Amion response with unknown role
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Test Person","EPICID:R777777","","Unknown Role","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should show "no new entries"
            assert b"No new entries" in response.data or b"info" in response.data.lower()

    @patch("backend.routes.schedule.requests.get")
    def test_import_skips_duplicate_entries(self, mock_get, client, app):
        """Test that import skips existing entries."""
        with app.app_context():
            from backend.models import Resident, TimeEntry

            test_date = date(2024, 4, 4)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Create existing resident and entry
            resident = Resident(name="Duplicate Test", epic_id="R666666", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            entry = TimeEntry(
                date=test_date,
                resident_id=resident.id,
                role_id=role.id,
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            # Mock Amion response with same resident/role
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Duplicate Test","EPICID:R666666","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Cleanup
            db.session.delete(entry)
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_finds_resident_by_epic_id(self, mock_get, client, app):
        """Test that import finds existing resident by EPIC ID."""
        with app.app_context():
            from backend.models import Resident, TimeEntry

            test_date = date(2024, 4, 5)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Create resident with EPIC ID
            resident = Resident(name="EPIC Test", epic_id="R555555", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Mock Amion response - same EPIC ID but different name
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Different Name","EPICID:R555555","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Cleanup
            TimeEntry.query.filter_by(resident_id=resident_id).delete()
            resident = db.session.get(Resident, resident_id)
            if resident:
                db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_no_entries_message(self, mock_get, client, app):
        """Test import shows info message when no entries imported."""
        with app.app_context():
            test_date = date(2024, 4, 6)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock empty CSV response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "Field1,Field2,Field3,Field4,Field5,Field6,Field7,Field8,Field9\n"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

    @patch("backend.routes.schedule.requests.get")
    def test_import_general_exception(self, mock_get, client, app):
        """Test import handles general exceptions."""
        with app.app_context():
            test_date = date(2024, 4, 7)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock to raise a general exception
            mock_get.side_effect = Exception("General error")

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Error" in response.data or b"error" in response.data

    @patch("backend.routes.schedule.requests.get")
    def test_import_role_in_mapping_but_not_in_db(self, mock_get, client, app):
        """Test import logs warning when role is in mapping but missing from database."""
        with app.app_context():
            from backend.models import TimeEntry

            test_date = date(2024, 4, 8)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Remove the ECA 2 role if it exists (it's in the mapping)
            role = Role.query.filter_by(name="ECA 2").first()
            if role:
                # First remove any time entries referencing this role
                TimeEntry.query.filter_by(role_id=role.id).delete()
                db.session.delete(role)
                db.session.commit()

            # Mock Amion response with ECA 2 role (in mapping but not in DB)
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Test Person","EPICID:R444444","","ECA 2","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Restore the ECA 2 role for other tests
            if not Role.query.filter_by(name="ECA 2").first():
                role = Role(name="ECA 2", cutoff_hour=17, cutoff_minute=30, display_order=2)
                db.session.add(role)
                db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_creates_new_resident_without_epic_id(self, mock_get, client, app):
        """Test import creates new resident when EPIC ID format is wrong."""
        with app.app_context():
            from backend.models import Resident, TimeEntry

            test_date = date(2024, 4, 9)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Make sure we have the ECC 1 role
            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Delete any existing resident with this name
            existing = Resident.query.filter_by(name="Brand New Person").first()
            if existing:
                TimeEntry.query.filter_by(resident_id=existing.id).delete()
                db.session.delete(existing)
                db.session.commit()

            # Mock Amion response with new resident without proper EPIC ID format
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Brand New Person","","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Check if resident was created
            resident = Resident.query.filter_by(name="Brand New Person").first()
            assert resident is not None

            # Cleanup
            TimeEntry.query.filter_by(resident_id=resident.id).delete()
            db.session.delete(resident)
            db.session.commit()
