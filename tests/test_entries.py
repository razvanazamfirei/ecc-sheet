"""Tests for entry routes."""

from datetime import time
from unittest.mock import patch

import pytest

from backend.models import AuditLog, DailySheet, TimeEntry, db
from backend.utils import get_effective_date


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
            entry = db.session.get(TimeEntry, entry_id)
            assert entry is not None
            assert entry.exit_time == time(21, 30)

    def test_update_exit_time_returns_json_for_async_requests(
        self, client, app, sample_time_entry
    ):
        """Test async entry updates return JSON instead of redirecting."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": "21:30"},
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            assert response.status_code == 200

            payload = response.get_json()
            assert payload is not None
            assert payload["success"] is True
            assert payload["entry"]["exit_time"] == "21:30"
            assert payload["entry"]["overtime_display"].endswith("hrs")

    def test_async_update_returns_json_for_csrf_failures(
        self, client, app, sample_time_entry
    ):
        """Async saves should receive JSON instead of an HTML CSRF page."""
        original_csrf_enabled = app.config["WTF_CSRF_ENABLED"]
        app.config["WTF_CSRF_ENABLED"] = True

        try:
            response = client.post(
                f"/entries/{sample_time_entry.id}/update",
                data={"exit_time": "21:30"},
                headers={
                    "Accept": "application/json",
                    "X-Expect-JSON": "1",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
        finally:
            app.config["WTF_CSRF_ENABLED"] = original_csrf_enabled

        assert response.status_code == 400
        payload = response.get_json()
        assert payload is not None
        assert payload["success"] is False
        assert "Reload the page and try again" in payload["message"]

    def test_update_all_returns_json_for_async_requests(
        self, client, app, sample_time_entry
    ):
        """Bulk save should update multiple rows in one JSON request."""
        with app.app_context():
            sample_entry_id = sample_time_entry.id
            extra_entry = TimeEntry(
                date=sample_time_entry.date,
                resident_id=sample_time_entry.resident_id,
                role_id=sample_time_entry.role_id,
                exit_time=time(19, 0),
            )
            db.session.add(extra_entry)
            db.session.commit()

            sheet = DailySheet.query.filter_by(date=sample_time_entry.date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                "/entries/update-all",
                json={
                    "entries": [
                        {"id": sample_entry_id, "exit_time": "21:30"},
                        {"id": extra_entry.id, "exit_time": "22:00"},
                    ]
                },
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            assert response.status_code == 200
            payload = response.get_json()
            assert payload is not None
            assert payload["success"] is True
            assert [entry["id"] for entry in payload["entries"]] == [
                sample_entry_id,
                extra_entry.id,
            ]

            updated_sample_entry = db.session.get(TimeEntry, sample_entry_id)
            assert updated_sample_entry is not None
            db.session.refresh(extra_entry)
            assert updated_sample_entry.exit_time == time(21, 30)
            assert extra_entry.exit_time == time(22, 0)

            db.session.delete(extra_entry)
            db.session.commit()

    def test_update_all_is_atomic_when_an_entry_is_missing(
        self, client, app, sample_time_entry
    ):
        """Bulk save should not partially apply updates when validation fails."""
        with app.app_context():
            sample_entry_id = sample_time_entry.id
            original_exit_time = sample_time_entry.exit_time

            response = client.post(
                "/entries/update-all",
                json={
                    "entries": [
                        {"id": sample_entry_id, "exit_time": "21:30"},
                        {"id": 999999, "exit_time": "22:00"},
                    ]
                },
                headers={
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )

            assert response.status_code == 404
            payload = response.get_json()
            assert payload is not None
            assert payload["success"] is False

            unchanged_entry = db.session.get(TimeEntry, sample_entry_id)
            assert unchanged_entry is not None
            assert unchanged_entry.exit_time == original_exit_time

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

            entry = db.session.get(TimeEntry, entry_id)
            assert entry is not None
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

    # noinspection DuplicatedCode
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
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=get_effective_date()).first()
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
            entry = db.session.get(TimeEntry, entry_id)
            assert entry is not None
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
            assert role is not None

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=get_effective_date()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                "/entries/add",
                data={
                    "date": get_effective_date().strftime("%Y-%m-%d"),
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
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=role.id,
            ).first()
            assert entry is not None

            # Cleanup
            db.session.delete(entry)
            db.session.commit()


class TestEntryDelete:
    """Tests for deleting entries."""

    def test_delete_nonexistent_entry(self, client):
        """Test deleting a nonexistent entry returns 404."""
        import werkzeug.exceptions
        import werkzeug.routing.exceptions

        try:
            response = client.post("/entries/99999/delete")
            assert response.status_code == 404
        except (werkzeug.exceptions.NotFound, werkzeug.routing.exceptions.BuildError):
            # 404 raised directly or BuildError from redirect is acceptable
            pass

    def test_delete_entry_success(self, client, app, sample_time_entry):
        """Test successfully deleting an entry."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"deleted" in response.data.lower()


class TestEntryAuditLogging:
    """Tests that entry mutations persist audit logs."""

    def test_add_entry_creates_audit_log(
        self, client, app, sample_resident, sample_role
    ):
        """Test adding an entry creates a persisted audit record."""
        with app.app_context():
            entry_date = get_effective_date()
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                "/entries/add",
                data={
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "resident_id": sample_resident.id,
                    "role_id": sample_role.id,
                    "exit_time": "20:00",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            entry = (
                TimeEntry.query.filter_by(
                    date=entry_date,
                    resident_id=sample_resident.id,
                    role_id=sample_role.id,
                )
                .order_by(TimeEntry.id.desc())
                .first()
            )
            assert entry is not None

            log = (
                AuditLog.query.filter_by(
                    entity_type="TimeEntry", entity_id=entry.id, action="CREATE"
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None

            db.session.delete(log)
            db.session.delete(entry)
            db.session.commit()

    def test_update_entry_creates_audit_log(self, client, app, sample_time_entry):
        """Test updating an entry creates a persisted audit record."""
        with app.app_context():
            entry_date = sample_time_entry.date
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{sample_time_entry.id}/update",
                data={"exit_time": "21:15"},
                follow_redirects=True,
            )
            assert response.status_code == 200

            log = (
                AuditLog.query.filter_by(
                    entity_type="TimeEntry",
                    entity_id=sample_time_entry.id,
                    action="UPDATE",
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None
            assert "21:15" in (log.details or "")

            db.session.delete(log)
            db.session.commit()

    def test_delete_entry_creates_audit_log(self, client, app, sample_time_entry):
        """Test deleting an entry creates a persisted audit record."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/entries/{entry_id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200

            log = (
                AuditLog.query.filter_by(
                    entity_type="TimeEntry", entity_id=entry_id, action="DELETE"
                )
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None

            db.session.delete(log)
            db.session.commit()


class TestEntryEdgeCases:
    """Edge case tests for entries."""

    def test_update_nonexistent_entry(self, client):
        """Test updating a nonexistent entry returns 404."""
        import werkzeug.exceptions
        import werkzeug.routing.exceptions

        try:
            response = client.post(
                "/entries/99999/update",
                data={"exit_time": "20:00"},
            )
            assert response.status_code == 404
        except (werkzeug.exceptions.NotFound, werkzeug.routing.exceptions.BuildError):
            # 404 raised directly or BuildError from redirect is acceptable
            pass

    def test_add_entry_invalid_date(self, client, app, sample_resident, sample_role):
        """Test adding entry with invalid date."""
        with app.app_context():
            response = client.post(
                "/entries/add",
                data={
                    "date": "invalid-date",
                    "resident_id": sample_resident.id,
                    "role_id": sample_role.id,
                    "exit_time": "20:00",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should show error
            assert b"error" in response.data.lower()

    def test_update_entry_clears_start_time(self, client, app, sample_resident):
        """Test clearing start time on entry."""
        with app.app_context():
            from backend.models import Role

            role = Role.query.first()
            assert role is not None

            # Create entry with start time
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=role.id,
                exit_time=time(20, 0),
                start_time=time(8, 0),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=get_effective_date()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Update with empty start time
            response = client.post(
                f"/entries/{entry_id}/update",
                data={"exit_time": "20:00", "start_time": ""},
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify start time cleared
            entry = db.session.get(TimeEntry, entry_id)
            assert entry is not None
            assert entry.start_time is None

            # Cleanup
            db.session.delete(entry)
            db.session.commit()

    def test_add_entry_with_no_resident(self, client, app, sample_role):
        """Test adding entry without resident fails gracefully."""
        with app.app_context():
            from backend.models import TimeEntry

            # Get initial entry count
            initial_count = TimeEntry.query.count()

            response = client.post(
                "/entries/add",
                data={
                    "date": get_effective_date().strftime("%Y-%m-%d"),
                    "resident_id": "",
                    "role_id": sample_role.id,
                    "exit_time": "20:00",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify no new entry was created
            final_count = TimeEntry.query.count()
            assert final_count == initial_count
            # Should show error message
            assert (
                b"required" in response.data.lower()
                or b"error" in response.data.lower()
            )


class TestEntryPermissions:
    """Tests that non-first-call, non-admin users cannot modify entries."""

    @pytest.fixture(autouse=True)
    def _restrict_user(self, monkeypatch):
        monkeypatch.setenv("USER_NAME", "Regular Viewer")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

    def test_add_blocked_for_non_first_call(
        self, client, app, sample_resident, sample_role
    ):
        """Non-admin, non-first-call user cannot add entries."""
        with app.app_context():
            response = client.post(
                "/entries/add",
                data={
                    "date": get_effective_date().strftime("%Y-%m-%d"),
                    "resident_id": sample_resident.id,
                    "role_id": sample_role.id,
                    "exit_time": "20:00",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"first call" in response.data.lower()

    def test_update_blocked_for_non_first_call(self, client, app, sample_time_entry):
        """Non-admin, non-first-call user cannot update entries."""
        with app.app_context():
            response = client.post(
                f"/entries/{sample_time_entry.id}/update",
                data={"exit_time": "21:00"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"first call" in response.data.lower()

    def test_delete_blocked_for_non_first_call(self, client, app, sample_time_entry):
        """Non-admin, non-first-call user cannot delete entries."""
        with app.app_context():
            response = client.post(
                f"/entries/{sample_time_entry.id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"first call" in response.data.lower()

            # Entry should still exist
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            assert entry is not None


class TestEntryExceptionHandling:
    """Tests for exception handling in entry routes."""

    def test_update_entry_db_error(self, client, app, sample_time_entry):
        """Test update handles database errors gracefully."""
        with app.app_context():
            entry_id = sample_time_entry.id
            entry_date = sample_time_entry.date

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=entry_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    f"/entries/{entry_id}/update",
                    data={"exit_time": "21:30"},
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()

    # noinspection DuplicatedCode
    def test_delete_entry_db_error(self, client, app, sample_resident, sample_role):
        """Test delete handles database errors gracefully."""
        with app.app_context():
            # Create a fresh entry for this test
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=get_effective_date()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock commit to raise an exception (simulating error during delete)
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    f"/entries/{entry_id}/delete",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()

            # Clean up the entry since delete failed
            db.session.rollback()
            entry = db.session.get(TimeEntry, entry_id)
            if entry:
                db.session.delete(entry)
                db.session.commit()

    def test_add_entry_db_error(self, client, app, sample_resident, sample_role):
        """Test add handles database errors gracefully."""
        with app.app_context():
            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=get_effective_date()).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    "/entries/add",
                    data={
                        "date": get_effective_date().strftime("%Y-%m-%d"),
                        "resident_id": sample_resident.id,
                        "role_id": sample_role.id,
                        "exit_time": "20:00",
                    },
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()
