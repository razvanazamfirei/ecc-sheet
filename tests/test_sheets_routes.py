"""Tests for sheet routes."""

from datetime import timedelta
from unittest.mock import patch

from backend.models import DailySheet, TimeEntry, db
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


class TestSheetsView:
    """Tests for viewing specific date sheets."""

    def test_view_past_date(self, client, app):
        """Test viewing a past date sheet."""
        past_date = get_effective_date() - timedelta(days=7)
        date_str = past_date.strftime("%Y-%m-%d")

        response = client.get(f"/sheets/{date_str}")
        assert response.status_code == 200
        assert past_date.strftime("%B %d, %Y").encode() in response.data

    def test_view_future_date(self, client, app):
        """Test viewing a future date sheet."""
        future_date = get_effective_date() + timedelta(days=7)
        date_str = future_date.strftime("%Y-%m-%d")

        response = client.get(f"/sheets/{date_str}")
        assert response.status_code == 200
        assert future_date.strftime("%B %d, %Y").encode() in response.data

    def test_view_invalid_date_format(self, client, app):
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
