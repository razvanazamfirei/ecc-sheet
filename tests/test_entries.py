"""Tests for entry routes."""

from datetime import date, time

import pytest

from backend.models import DailySheet, TimeEntry, db


class TestEntryUpdate:
    """Tests for entry update functionality."""

    def test_update_exit_time(self, client, app, sample_time_entry):
        """Test updating exit time."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": "21:30"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify update
            entry = TimeEntry.query.get(entry_id)
            assert entry.exit_time == time(21, 30)

    def test_update_clears_exit_time(self, client, app, sample_time_entry):
        """Test clearing exit time."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": ""},
                follow_redirects=True,
            )
            assert response.status_code == 200

            entry = TimeEntry.query.get(entry_id)
            assert entry.exit_time is None

    def test_update_locked_sheet_fails(self, client, app, sample_time_entry):
        """Test that updating entry on locked sheet fails."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            # Lock the sheet
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if not sheet:
                sheet = DailySheet(date=entry_date, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": "22:00"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"locked" in response.data.lower()

            # Unlock for cleanup
            sheet.locked = False
            db.session.commit()

    def test_update_with_start_time(self, client, app, sample_resident):
        """Test updating entry with start time for backup role."""
        with app.app_context():
            from backend.models import Role

            # Get or create a backup role
            backup_role = Role.query.filter_by(is_backup=True).first()
            if not backup_role:
                backup_role = Role(
                    name="Test Backup",
                    cutoff_hour=17,
                    cutoff_minute=30,
                    is_backup=True,
                    display_order=100,
                )
                db.session.add(backup_role)
                db.session.commit()

            # Create entry with backup role
            entry = TimeEntry(
                date=date.today(),
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=date.today()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Update with start time
            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": "20:00", "start_time": "09:00"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify
            entry = TimeEntry.query.get(entry_id)
            assert entry.start_time == time(9, 0)

            # Cleanup
            db.session.delete(entry)
            db.session.commit()


class TestEntryAdd:
    """Tests for adding entries."""

    def test_add_entry_with_start_time(self, client, app, sample_resident):
        """Test adding entry with start time."""
        with app.app_context():
            from backend.models import Role

            role = Role.query.first()

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=date.today()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                "/entries/add",
                data={
                    "date": date.today().strftime("%Y-%m-%d"),
                    "resident_id": sample_resident.id,
                    "role_id": role.id,
                    "exit_time": "19:00",
                    "start_time": "08:00",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify entry was created
            entry = TimeEntry.query.filter_by(
                date=date.today(),
                resident_id=sample_resident.id,
                role_id=role.id,
            ).first()
            assert entry is not None

            # Cleanup
            if entry:
                db.session.delete(entry)
                db.session.commit()
