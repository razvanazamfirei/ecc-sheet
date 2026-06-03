"""Tests for schedule import functionality."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.models import AuditLog, DailySheet, Resident, Role, TimeEntry, db


@pytest.mark.integration
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

            resident = Resident(
                name="Test Resident",
                epic_id="R12345",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            # Mock the Amion response with valid CSV data
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Test Resident","EPICID:R12345","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Successfully imported" in response.data
            assert mock_get.call_args is not None
            assert mock_get.call_args.args[0].startswith("https://")
            assert (
                TimeEntry.query.filter_by(
                    date=test_date, resident_id=resident.id, role_id=role.id
                ).first()
                is not None
            )

            TimeEntry.query.filter_by(resident_id=resident.id, date=test_date).delete()
            db.session.delete(resident)
            db.session.commit()

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
            assert b"Error fetching data from Amion." in response.data
            assert b"Network error" not in response.data

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

    @patch("backend.routes.schedule.requests.get")
    def test_import_skips_unknown_residents(self, mock_get, client, app):
        """Test that import skips rows for residents who are not in the database."""
        with app.app_context():
            test_date = date(2024, 4, 1)
            unknown_resident_name = "Unknown Resident 99999"

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
                f'"{unknown_resident_name}","EPICID:R999999","","ECC 1","","","",'
                '"",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"resident was not found" in response.data
            assert Resident.query.filter_by(epic_id="R999999").first() is None

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
    def test_import_skips_name_match_when_epic_id_conflicts(
        self, mock_get, client, app
    ):
        """Test import skips name matches when the EPIC ID belongs to someone else."""
        with app.app_context():
            test_date = date(2024, 4, 12)

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            resident = Resident(
                name="Conflict Resident",
                epic_id="R565656",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Conflict Resident","EPICID:R575757","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"different EPIC ID" in response.data

            resident = db.session.get(Resident, resident_id)
            assert resident is not None
            assert resident.epic_id == "R565656"
            assert (
                TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident.id,
                ).first()
                is None
            )

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
            assert (
                b"No new entries" in response.data or b"info" in response.data.lower()
            )

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
            mock_response.text = (
                "Field1,Field2,Field3,Field4,Field5,Field6,Field7,Field8,Field9\n"
            )
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
        """Test import warning when role is in mapping but missing from database."""
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
            mock_response.text = '"Test Person","","","ECA 2","","","","",""\n'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert Resident.query.filter_by(name="Test Person").first() is None

            # Restore the ECA 2 role for other tests
            if not Role.query.filter_by(name="ECA 2").first():
                role = Role(
                    name="ECA 2", cutoff_hour=17, cutoff_minute=30, display_order=2
                )
                db.session.add(role)
                db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_uses_existing_resident_without_epic_id(self, mock_get, client, app):
        """Test import matches an existing resident by name when EPIC is absent."""
        with app.app_context():
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

            resident = Resident(name="Brand New Person", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            # Mock Amion response without a valid EPIC ID so name matching is used.
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '"Brand New Person","","","ECC 1","","","","",""\n'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = db.session.get(Resident, resident_id)
            assert resident is not None
            assert resident.epic_id is None
            assert (
                TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident.id,
                ).first()
                is not None
            )

            # Cleanup
            TimeEntry.query.filter_by(resident_id=resident.id).delete()
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_creates_name_only_resident_and_audit_logs_it(
        self, mock_get, client, app
    ):
        """Test import creates a resident when a matching name-only row is new."""
        with app.app_context():
            test_date = date(2024, 4, 11)

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '"Walk In Resident","","","ECC 1","","","","",""\n'
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = Resident.query.filter_by(name="Walk In Resident").first()
            assert resident is not None
            assert resident.epic_id is None

            entry = TimeEntry.query.filter_by(
                date=test_date,
                resident_id=resident.id,
            ).first()
            assert entry is not None

            resident_log = (
                AuditLog.query.filter_by(
                    entity_type="Resident",
                    entity_id=resident.id,
                    action="CREATE",
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            entry_log = (
                AuditLog.query.filter_by(
                    entity_type="TimeEntry",
                    entity_id=entry.id,
                    action="CREATE",
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert resident_log is not None
            assert entry_log is not None

            db.session.delete(resident_log)
            db.session.delete(entry_log)
            db.session.delete(entry)
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_skips_weekday_backup_when_resident_is_also_late(
        self, mock_get, client, app
    ):
        """Test weekday imports skip Backup when the resident is also a Late."""
        with app.app_context():
            test_date = date(2024, 4, 1)  # Monday, non-holiday

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            for role_name in ("Late Late 1", "Backup"):
                role = Role.query.filter_by(name=role_name).first()
                assert role is not None

            resident = Resident(
                name="Overlap Resident",
                epic_id="R424242",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Overlap Resident","EPICID:R424242","","Late Late 1","","","","",""\n'
                '"Overlap Resident","EPICID:R424242","","Backup","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = db.session.get(Resident, resident_id)
            assert resident is not None

            entries = (
                TimeEntry.query.filter_by(date=test_date, resident_id=resident.id)
                .order_by(TimeEntry.id)
                .all()
            )
            role_names = {
                db.session.get(Role, entry.role_id).name
                for entry in entries
                if entry.role_id is not None
            }
            assert role_names == {"Late Late 1"}

            TimeEntry.query.filter_by(resident_id=resident.id).delete()
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_reports_skipped_weekday_backups_when_no_entries_created(
        self, mock_get, client, app
    ):
        """Test no-entry imports report weekday-backup skips."""
        with app.app_context():
            test_date = date(2024, 4, 15)  # Monday, non-holiday

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            late_role = Role.query.filter_by(name="Late Late 1").first()
            backup_role = Role.query.filter_by(name="Backup").first()
            assert late_role is not None
            assert backup_role is not None

            resident = Resident(
                name="No New Entries",
                epic_id="R424243",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            existing_entry = TimeEntry(
                date=test_date,
                resident_id=resident_id,
                role_id=late_role.id,
                exit_time=None,
            )
            db.session.add(existing_entry)
            db.session.commit()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"No New Entries","EPICID:R424243","","Late Late 1","","","","",""\n'
                '"No New Entries","EPICID:R424243","","Backup","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"No new entries imported" in response.data
            assert b"weekday-backup rules" in response.data

            entries = TimeEntry.query.filter_by(
                date=test_date,
                resident_id=resident_id,
            ).all()
            assert len(entries) == 1
            assert entries[0].role_id == late_role.id

            db.session.delete(existing_entry)
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_keeps_backup_on_weekend_even_if_resident_is_also_late(
        self, mock_get, client, app
    ):
        """Test weekend imports keep Backup even when the resident is also a Late."""
        with app.app_context():
            test_date = date(2024, 4, 6)  # Saturday

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            resident = Resident(
                name="Weekend Overlap",
                epic_id="R434343",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Weekend Overlap","EPICID:R434343","","Late Late 1","","","","",""\n'
                '"Weekend Overlap","EPICID:R434343","","Backup","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = db.session.get(Resident, resident_id)
            assert resident is not None

            entries = (
                TimeEntry.query.filter_by(date=test_date, resident_id=resident.id)
                .order_by(TimeEntry.id)
                .all()
            )
            role_names = {
                db.session.get(Role, entry.role_id).name
                for entry in entries
                if entry.role_id is not None
            }
            assert role_names == {"Late Late 1", "Backup"}

            TimeEntry.query.filter_by(resident_id=resident.id).delete()
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_creates_audit_logs(self, mock_get, client, app):
        """Test schedule imports persist resident, entry, and import audit logs."""
        with app.app_context():
            test_date = date(2024, 4, 10)

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            resident = Resident(name="Audit Schedule", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id
            AuditLog.query.filter_by(
                entity_type="Resident",
                entity_id=resident_id,
                action="UPDATE",
            ).delete()
            db.session.commit()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Audit Schedule","EPICID:R454545","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

            resident = db.session.get(Resident, resident_id)
            assert resident is not None
            assert resident.epic_id == "R454545"
            entry = TimeEntry.query.filter_by(
                date=test_date, resident_id=resident.id
            ).first()
            assert entry is not None

            resident_log = (
                AuditLog.query.filter_by(
                    entity_type="Resident", entity_id=resident.id, action="UPDATE"
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            entry_log = (
                AuditLog.query.filter_by(
                    entity_type="TimeEntry", entity_id=entry.id, action="CREATE"
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            import_log = (
                AuditLog.query.filter_by(entity_type="Schedule", action="IMPORT")
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert resident_log is None
            assert entry_log is not None
            assert import_log is not None

            db.session.delete(entry_log)
            db.session.delete(import_log)
            db.session.delete(entry)
            db.session.delete(resident)
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_rolls_back_when_audit_logging_raises(self, mock_get, client, app):
        """Test audit failures roll back schedule changes before commit."""
        with app.app_context():
            test_date = date(2024, 4, 13)

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            resident = Resident(name="Audit Rollback", active=True)
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Audit Rollback","EPICID:R454546","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            with patch(
                "backend.routes.schedule.log_import_strict",
                side_effect=RuntimeError("audit failure"),
            ):
                response = client.post(
                    f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                    follow_redirects=True,
                )

            assert response.status_code == 200
            assert b"Error importing schedule." in response.data
            assert b"audit failure" not in response.data

            resident = db.session.get(Resident, resident_id)
            assert resident is not None
            assert resident.epic_id is None
            assert (
                TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident_id,
                ).first()
                is None
            )

            db.session.delete(resident)
            db.session.commit()


@patch("backend.routes.schedule.requests.get")
@pytest.mark.integration
def test_import_supports_first_call_role_aliases(mock_get, client, app, monkeypatch):
    """Test configured first-call aliases are treated as importable roles."""
    monkeypatch.setitem(app.config, "FIRST_CALL_ROLES", "Custom First Call")

    with app.app_context():
        test_date = date(2024, 4, 14)

        sheet = DailySheet.query.filter_by(date=test_date).first()
        if sheet:
            sheet.locked = False
            db.session.commit()

        role = Role.query.filter_by(name="Custom First Call").first()
        created_role = role is None
        if role is None:
            role = Role(
                name="Custom First Call",
                cutoff_hour=17,
                cutoff_minute=30,
                display_order=250,
                is_call_team=True,
            )
            db.session.add(role)
            db.session.commit()

        resident = Resident(
            name="Alias Call Resident",
            epic_id="R121212",
            active=True,
        )
        db.session.add(resident)
        db.session.commit()
        resident_id = resident.id

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            '"Alias Call Resident","EPICID:R121212","","Custom First Call",'
            '"","","","",""\n'
        )
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = client.post(
            f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert (
            TimeEntry.query.filter_by(
                date=test_date,
                resident_id=resident_id,
                role_id=role.id,
            ).first()
            is not None
        )

        TimeEntry.query.filter_by(date=test_date, resident_id=resident_id).delete()
        db.session.delete(db.session.get(Resident, resident_id))
        if created_role:
            db.session.delete(role)
        db.session.commit()


@patch("backend.routes.schedule.requests.get")
@pytest.mark.integration
def test_import_includes_full_call_team(mock_get, client, app):
    """Second/third/cardiac/OB call-team roles are imported from Amion."""
    with app.app_context():
        test_date = date(2024, 4, 16)

        sheet = DailySheet.query.filter_by(date=test_date).first()
        if sheet:
            sheet.locked = False
            db.session.commit()

        residents_by_role = {
            "First Call": ("First Call Resident", "R710001"),
            "Second Call": ("Second Call Resident", "R710002"),
            "Third Call": ("Third Call Resident", "R710003"),
            "Cardiac Call": ("Cardiac Call Resident", "R710004"),
            "OB Flex": ("OB Flex Resident", "R710005"),
        }

        residents: list[Resident] = []
        for resident_name, epic_id in residents_by_role.values():
            resident = Resident(name=resident_name, epic_id=epic_id, active=True)
            db.session.add(resident)
            residents.append(resident)
        db.session.commit()

        csv_lines = []
        for role_name, (resident_name, epic_id) in residents_by_role.items():
            role = Role.query.filter_by(name=role_name).first()
            assert role is not None
            csv_lines.append(
                f'"{resident_name}","EPICID:{epic_id}","","{role_name}","","","","",""'
            )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "\n".join(csv_lines) + "\n"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        response = client.post(
            f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Successfully imported 5 schedule entries from Amion" in response.data

        for role_name, (resident_name, _epic_id) in residents_by_role.items():
            resident = Resident.query.filter_by(name=resident_name).first()
            role = Role.query.filter_by(name=role_name).first()
            assert resident is not None
            assert role is not None
            assert (
                TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident.id,
                    role_id=role.id,
                ).first()
                is not None
            )

        TimeEntry.query.filter(
            TimeEntry.date == test_date,
            TimeEntry.resident_id.in_([resident.id for resident in residents]),
        ).delete(synchronize_session=False)
        for resident in residents:
            persisted_resident = db.session.get(Resident, resident.id)
            if persisted_resident is not None:
                db.session.delete(persisted_resident)
        db.session.commit()


@pytest.mark.integration
def test_import_invalid_date(client):
    """Test import with invalid date format."""
    response = client.post(
        "/schedule/invalid-date/import",
        follow_redirects=True,
    )
    assert response.status_code in {200, 400, 404}


@patch("backend.routes.schedule.requests.get")
@pytest.mark.integration
def test_import_requires_editor_role(mock_get, client, app, monkeypatch):
    """Regular non-editor users cannot trigger schedule imports."""
    monkeypatch.setitem(app.config, "USER_NAME", "Regular User")
    monkeypatch.setitem(app.config, "ADMIN_USERS", "Admin Only")
    test_date = date(2024, 4, 7)

    with app.app_context():
        first_call_role = Role.query.filter_by(name="First Call").first()
        if first_call_role is None:
            first_call_role = Role(
                name="First Call",
                cutoff_hour=17,
                cutoff_minute=30,
                is_call_team=True,
            )
            db.session.add(first_call_role)
            db.session.commit()

        first_call_resident = Resident(name="Assigned First Call", active=True)
        db.session.add(first_call_resident)
        db.session.commit()

        first_call_entry = TimeEntry(
            date=test_date,
            resident_id=first_call_resident.id,
            role_id=first_call_role.id,
            exit_time=None,
        )
        db.session.add(first_call_entry)
        db.session.commit()
        first_call_resident_id = first_call_resident.id
        first_call_role_id = first_call_role.id

    try:
        response = client.post(
            f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert (
            b"Only the first call resident or an admin can import schedules"
            in response.data
        )
        mock_get.assert_not_called()
    finally:
        with app.app_context():
            persisted_entry = TimeEntry.query.filter_by(
                date=test_date,
                resident_id=first_call_resident_id,
                role_id=first_call_role_id,
            ).first()
            if persisted_entry is not None:
                db.session.delete(persisted_entry)
            persisted_resident = db.session.get(Resident, first_call_resident_id)
            if persisted_resident is not None:
                db.session.delete(persisted_resident)
            db.session.commit()
