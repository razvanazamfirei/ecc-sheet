"""Tests for sheet routes."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytz

from backend.models import DailySheet, Resident, Role, TimeEntry, db
from backend.utils import get_effective_date


class TestSheetsIndex:
    """Tests for the sheets index page."""

    def test_index_creates_daily_sheet_if_not_exists(self, client, app):
        """Test that index creates daily sheet if it doesn't exist."""
        with app.app_context():
            today = get_effective_date()
            # Delete existing sheet
            DailySheet.query.filter_by(date=today).delete()
            db.session.commit()

            response = client.get("/")
            assert response.status_code == 200

            # Sheet should now exist
            sheet = DailySheet.query.filter_by(date=today).first()
            assert sheet is not None

    def test_index_shows_roles(self, client, app, sample_role):
        """Test that index shows available roles."""
        with app.app_context():
            response = client.get("/")
            assert response.status_code == 200
            assert sample_role.name.encode() in response.data

    def test_index_shows_navigation_links(self, client):
        """Test that index shows navigation links."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Previous Day" in response.data
        assert b"Today" in response.data
        assert b"Next Day" in response.data

    def test_index_shows_lock_button(self, client):
        """Test that index shows lock/unlock button."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Lock Sheet" in response.data or b"Unlock Sheet" in response.data

    def test_index_shows_import_button_for_regular_user(self, client, monkeypatch):
        """Regular users still see schedule import even without edit rights."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/")
        assert response.status_code == 200
        assert b"Import Schedule" in response.data
        assert b"Add New Entry" not in response.data
        assert b"Lock Sheet" not in response.data
        assert b"Unlock Sheet" not in response.data


class TestSheetsView:
    """Tests for viewing specific date sheets."""

    def test_view_past_date(self, client):
        """Test viewing a past date sheet."""
        past_date = get_effective_date() - timedelta(days=7)
        date_str = past_date.strftime("%Y-%m-%d")

        response = client.get(f"/sheets/{date_str}")
        assert response.status_code == 200
        assert past_date.strftime("%B %d, %Y").encode() in response.data

    def test_view_future_date(self, client):
        """Test viewing a future date sheet."""
        future_date = get_effective_date() + timedelta(days=7)
        date_str = future_date.strftime("%Y-%m-%d")

        response = client.get(f"/sheets/{date_str}")
        assert response.status_code == 200
        assert future_date.strftime("%B %d, %Y").encode() in response.data

    def test_view_invalid_date_format(self, client):
        """Test viewing with invalid date format redirects."""
        response = client.get("/sheets/invalid-date", follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid date format" in response.data

    def test_view_creates_sheet_if_not_exists(self, client, app):
        """Test that viewing creates sheet if it doesn't exist."""
        with app.app_context():
            # Use a date far in the future
            future_date = get_effective_date() + timedelta(days=100)
            date_str = future_date.strftime("%Y-%m-%d")

            # Ensure no sheet exists
            DailySheet.query.filter_by(date=future_date).delete()
            db.session.commit()

            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200

            # Sheet should now exist
            sheet = DailySheet.query.filter_by(date=future_date).first()
            assert sheet is not None

            # Cleanup
            db.session.delete(sheet)
            db.session.commit()

    def test_view_shows_entries_for_date(
        self, client, app, sample_resident, sample_role
    ):
        """Test that view shows entries for the specific date."""
        with app.app_context():
            test_date = get_effective_date() - timedelta(days=5)
            date_str = test_date.strftime("%Y-%m-%d")

            # Create entry for this date
            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
            )
            db.session.add(entry)
            db.session.commit()

            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200
            assert sample_resident.name.encode() in response.data

            # Cleanup
            db.session.delete(entry)
            db.session.commit()

    def test_auto_lock_warning_only_shows_on_previous_calendar_day(self, client):
        """The 8 AM banner should appear on the previous calendar day's sheet."""
        philly_tz = pytz.timezone("America/New_York")
        current_time = philly_tz.localize(datetime(2026, 3, 9, 8, 21))

        with patch(
            "backend.routes.sheets.get_philadelphia_time",
            return_value=current_time,
        ):
            previous_response = client.get("/sheets/2026-03-08")
            current_response = client.get("/sheets/2026-03-09")

        assert b"This sheet will auto-lock at 09:00 AM" in previous_response.data
        assert b"This sheet will auto-lock at 09:00 AM" not in current_response.data

    def test_view_renders_lock_confirmation_fallback_when_exit_times_missing(
        self, client, app, sample_resident
    ):
        """Lock confirmation metadata should be present even before JS initializes."""
        with app.app_context():
            test_date = get_effective_date() + timedelta(days=30)
            overtime_role = Role.query.filter_by(name="ECC 1").first()
            assert overtime_role is not None
            overtime_role_id = overtime_role.id

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet is None:
                sheet = DailySheet(date=test_date, locked=False)
                db.session.add(sheet)
            else:
                sheet.locked = False

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=overtime_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()
            db.session.remove()

        try:
            response = client.get(f"/sheets/{test_date.strftime('%Y-%m-%d')}")

            assert response.status_code == 200
            html = response.data.decode()
            lock_form_index = html.index('id="lock-sheet-form"')
            lock_form_markup = html[lock_form_index : lock_form_index + 800]

            assert "data-confirm-title=" in lock_form_markup
            assert "data-confirm-message=" in lock_form_markup
            assert (
                "These residents will not receive overtime credit:"
                in lock_form_markup
            )
            assert sample_resident.name in lock_form_markup
            assert html.count('class="btn-close"') >= 1
        finally:
            with app.app_context():
                persisted_entry = TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=sample_resident.id,
                    role_id=overtime_role_id,
                ).first()
                if persisted_entry is not None:
                    db.session.delete(persisted_entry)
                persisted_sheet = DailySheet.query.filter_by(date=test_date).first()
                if persisted_sheet is not None:
                    db.session.delete(persisted_sheet)
                db.session.commit()

    def test_overtime_entries_are_sorted_by_role_then_resident(self, client, app):
        """Manual overtime additions should render in role/name order."""
        with app.app_context():
            sheet_date = get_effective_date() - timedelta(days=10)
            date_str = sheet_date.strftime("%Y-%m-%d")

            residents = [
                Resident(name="Sort Order Held Resident", active=True),
                Resident(name="Sort Order Zebra Resident", active=True),
                Resident(name="Sort Order Alpha Resident", active=True),
            ]
            db.session.add_all(residents)
            db.session.commit()

            ecc_role = Role.query.filter_by(name="ECC 1").first()
            held_role = Role.query.filter_by(name="Held").first()
            assert ecc_role is not None
            assert held_role is not None

            entries = [
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[0].id,
                    role_id=held_role.id,
                ),
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[1].id,
                    role_id=ecc_role.id,
                ),
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[2].id,
                    role_id=ecc_role.id,
                ),
            ]
            db.session.add_all(entries)
            db.session.commit()

            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200

            html = response.data.decode()
            alpha_index = html.index(f'id="entry-row-{entries[2].id}"')
            zebra_index = html.index(f'id="entry-row-{entries[1].id}"')
            held_index = html.index(f'id="entry-row-{entries[0].id}"')
            assert alpha_index < zebra_index < held_index

            for entry in entries:
                db.session.delete(entry)
            for resident in residents:
                db.session.delete(resident)
            db.session.commit()


class TestSheetsLock:
    """Tests for locking/unlocking sheets."""

    def test_lock_unlocked_sheet(self, client, app):
        """Test locking an unlocked sheet."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=today).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            response = client.post(
                f"/sheets/{date_str}/lock",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"locked" in response.data.lower()

            # Verify locked
            sheet = DailySheet.query.filter_by(date=today).first()
            assert sheet is not None
            assert sheet.locked is True

            # Cleanup - unlock
            sheet.locked = False
            db.session.commit()

    def test_unlock_locked_sheet(self, client, app):
        """Test unlocking a locked sheet."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Ensure sheet is locked
            sheet = DailySheet.query.filter_by(date=today).first()
            if not sheet:
                sheet = DailySheet(date=today, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            db.session.commit()

            response = client.post(
                f"/sheets/{date_str}/lock",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"unlocked" in response.data.lower()

            # Verify unlocked
            sheet = DailySheet.query.filter_by(date=today).first()
            assert sheet is not None
            assert sheet.locked is False

    def test_lock_records_user_and_time(self, client, app):
        """Test that locking records user and timestamp."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=today).first()
            if sheet:
                sheet.locked = False
                sheet.locked_by = None
                sheet.locked_at = None
                db.session.commit()

            client.post(f"/sheets/{date_str}/lock", follow_redirects=True)

            # Verify lock info
            sheet = DailySheet.query.filter_by(date=today).first()
            assert sheet is not None
            assert sheet.locked is True
            assert sheet.locked_by is not None
            assert sheet.locked_at is not None

            # Cleanup
            sheet.locked = False
            db.session.commit()

    def test_unlock_clears_user_and_time(self, client, app):
        """Test that unlocking clears user and timestamp."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Ensure sheet is locked with info
            sheet = DailySheet.query.filter_by(date=today).first()
            if not sheet:
                sheet = DailySheet(date=today, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            sheet.locked_by = "Test User"
            db.session.commit()

            client.post(f"/sheets/{date_str}/lock", follow_redirects=True)

            # Verify lock info cleared
            sheet = DailySheet.query.filter_by(date=today).first()
            assert sheet is not None
            assert sheet.locked is False
            assert sheet.locked_by is None
            assert sheet.locked_at is None

    def test_lock_creates_sheet_if_not_exists(self, client, app):
        """Test that locking creates sheet if it doesn't exist."""
        with app.app_context():
            # Use a unique date
            test_date = get_effective_date() - timedelta(days=200)
            date_str = test_date.strftime("%Y-%m-%d")

            # Ensure no sheet exists
            DailySheet.query.filter_by(date=test_date).delete()
            db.session.commit()

            response = client.post(
                f"/sheets/{date_str}/lock",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Sheet should now exist and be locked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            assert sheet is not None
            assert sheet.locked is True

            # Cleanup
            db.session.delete(sheet)
            db.session.commit()


class TestWeekendHolidayDisplay:
    """Tests for weekend/holiday display."""

    def test_weekend_indicated(self, client, app):
        """Test that weekends are indicated."""
        with app.app_context():
            # Find a Saturday
            today = get_effective_date()
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            saturday = today + timedelta(days=days_until_saturday)
            date_str = saturday.strftime("%Y-%m-%d")

            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200
            # Should indicate it's a weekend (check for weekend-related text)
            data_lower = response.data.decode().lower()
            assert "weekend" in data_lower or "saturday" in data_lower


class TestSheetsExceptionHandling:
    """Tests for exception handling in sheet routes."""

    def test_lock_sheet_db_error(self, client, app):
        """Test lock handles database errors gracefully."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Ensure sheet exists and is unlocked
            sheet = DailySheet.query.filter_by(date=today).first()
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
                db.session.commit()

            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()


class TestSheetLockPermissions:
    """Tests that lock/unlock requires first call or admin."""

    def test_lock_blocked_for_non_first_call(self, client, app, monkeypatch):
        """Non-admin, non-first-call user cannot lock/unlock the sheet."""
        monkeypatch.setenv("USER_NAME", "Regular Viewer")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
                db.session.commit()
            original_locked = sheet.locked

            response = client.post(
                f"/sheets/{date_str}/lock",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"first call" in response.data.lower()

            # Sheet state should be unchanged
            db.session.refresh(sheet)
            assert sheet.locked == original_locked


class TestCallTeamFiltering:
    """Tests for call-team role separation in the sheet context."""

    def test_call_team_entries_separated_from_overtime(self, client, app):
        """Call-team entries appear in call_team_entries, not overtime_entries."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            # Remove any leftovers from a previous failed run
            for name in (
                "CT Filter Call Role",
                "CT Filter OT Role",
                "CT Filter Test Resident",
            ):
                existing_role = Role.query.filter_by(name=name).first()
                if existing_role:
                    db.session.delete(existing_role)
                existing_resident = Resident.query.filter_by(name=name).first()
                if existing_resident:
                    db.session.delete(existing_resident)
            db.session.commit()

            resident = Resident(name="CT Filter Test Resident", active=True)
            db.session.add(resident)

            call_role = Role(
                name="CT Filter Call Role",
                is_call_team=True,
                display_order=99,
            )
            ot_role = Role(
                name="CT Filter OT Role",
                is_call_team=False,
                display_order=100,
            )
            db.session.add_all([call_role, ot_role])
            db.session.commit()

            call_entry = TimeEntry(
                date=today,
                resident_id=resident.id,
                role_id=call_role.id,
                exit_time=None,
            )
            ot_entry = TimeEntry(
                date=today,
                resident_id=resident.id,
                role_id=ot_role.id,
                exit_time=None,
            )
            db.session.add_all([call_entry, ot_entry])
            db.session.commit()
            call_entry_id = call_entry.id
            ot_entry_id = ot_entry.id

            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200

            html = response.data.decode()
            # The call-team section renders each entry as "ROLE_NAME:" (with colon).
            # Verify the call role appears in that format and the OT role does not.
            assert "CT Filter Call Role:" in html, (
                "Call-team role not in call-team section"
            )
            assert "CT Filter OT Role:" not in html, (
                "OT role must not appear in call-team section"
            )
            # The OT role should still appear on the page (entries table / dropdown).
            assert "CT Filter OT Role" in html

            # Cleanup
            db.session.delete(db.session.get(TimeEntry, call_entry_id))
            db.session.delete(db.session.get(TimeEntry, ot_entry_id))
            db.session.delete(call_role)
            db.session.delete(ot_role)
            db.session.delete(resident)
            db.session.commit()

    def test_call_team_roles_absent_from_overtime_roles(self, client, app):
        """Call-team roles must not appear in the overtime roles dropdown."""
        with app.app_context():
            call_role = Role(
                name="CT Dropdown Call Role",
                is_call_team=True,
                display_order=98,
            )
            db.session.add(call_role)
            db.session.commit()

            response = client.get("/")
            assert response.status_code == 200
            assert b"CT Dropdown Call Role" not in response.data

            db.session.delete(call_role)
            db.session.commit()
