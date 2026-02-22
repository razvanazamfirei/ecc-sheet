"""Tests for holiday management routes."""

import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from backend.models import Holiday, db
from backend.utils import get_effective_date


class TestHolidaysIndex:
    """Tests for holidays index page."""

    def test_holidays_index_requires_admin(self, client):
        """Test that holidays index requires admin privileges."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.get("/holidays", follow_redirects=True)
            assert b"Admin privileges required" in response.data
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_holidays_index_loads(self, client):
        """Test that holidays index page loads."""
        response = client.get("/holidays")
        assert response.status_code == 200
        assert b"Holiday" in response.data

    def test_holidays_index_lists_holidays(self, client, app):
        """Test that holidays are listed."""
        with app.app_context():
            holiday = Holiday(
                date=date(2025, 12, 25),
                name="Christmas Test",
                is_federal=False,
            )
            db.session.add(holiday)
            db.session.commit()

            response = client.get("/holidays")
            assert response.status_code == 200
            assert b"Christmas Test" in response.data

            db.session.delete(holiday)
            db.session.commit()


class TestAddHoliday:
    """Tests for adding holidays."""

    def test_add_holiday_success(self, client, app):
        """Test successfully adding a holiday."""
        with app.app_context():
            test_date = get_effective_date() + timedelta(days=365)
            date_str = test_date.strftime("%Y-%m-%d")

            response = client.post(
                "/holidays/add",
                data={"date": date_str, "name": "Test Holiday"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"added successfully" in response.data

            # Verify in database
            holiday = Holiday.query.filter_by(date=test_date).first()
            assert holiday is not None
            assert holiday.name == "Test Holiday"
            assert holiday.is_federal is False

            # Cleanup
            db.session.delete(holiday)
            db.session.commit()

    def test_add_holiday_missing_date(self, client):
        """Test adding holiday without date fails."""
        response = client.post(
            "/holidays/add",
            data={"date": "", "name": "Test Holiday"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower()

    def test_add_holiday_missing_name(self, client, app):
        """Test adding holiday without name fails."""
        with app.app_context():
            test_date = get_effective_date() + timedelta(days=400)
            date_str = test_date.strftime("%Y-%m-%d")

            response = client.post(
                "/holidays/add",
                data={"date": date_str, "name": ""},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"required" in response.data.lower()

    def test_add_holiday_duplicate_date(self, client, app):
        """Test adding holiday with duplicate date fails."""
        with app.app_context():
            # Find a date not already seeded as a federal holiday
            candidate = get_effective_date() + timedelta(days=400)
            max_candidate = candidate + timedelta(days=365)
            while Holiday.query.filter_by(date=candidate).first():
                candidate += timedelta(days=1)
                if candidate > max_candidate:
                    pytest.fail("Could not find a non-holiday date within search range")
            test_date = candidate
            date_str = test_date.strftime("%Y-%m-%d")

            # Add first holiday
            holiday = Holiday(date=test_date, name="First Holiday", is_federal=False)
            db.session.add(holiday)
            db.session.commit()

            # Try to add duplicate
            response = client.post(
                "/holidays/add",
                data={"date": date_str, "name": "Second Holiday"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"already exists" in response.data

            # Cleanup
            db.session.delete(holiday)
            db.session.commit()

    def test_add_holiday_requires_admin(self, client):
        """Test that adding holiday requires admin."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.post(
                "/holidays/add",
                data={"date": "2025-12-25", "name": "Test"},
                follow_redirects=True,
            )
            assert b"Admin privileges required" in response.data
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_add_holiday_exception_handling(self, client, app):
        """Test that exceptions during add are handled."""
        with app.app_context():
            # Invalid date format will raise an exception
            response = client.post(
                "/holidays/add",
                data={"date": "invalid-date", "name": "Test Holiday"},
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Error" in response.data or b"error" in response.data


class TestDeleteHoliday:
    """Tests for deleting holidays."""

    def test_delete_holiday_success(self, client, app):
        """Test successfully deleting a holiday."""
        with app.app_context():
            holiday = Holiday(
                date=date(2030, 1, 1),
                name="Delete Test Holiday",
                is_federal=False,
            )
            db.session.add(holiday)
            db.session.commit()
            holiday_id = holiday.id

            response = client.post(
                f"/holidays/{holiday_id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"deleted successfully" in response.data

            # Verify deleted
            deleted_holiday = db.session.get(Holiday, holiday_id)
            assert deleted_holiday is None

    def test_delete_nonexistent_holiday(self, client):
        """Test deleting nonexistent holiday returns 404."""
        import werkzeug.exceptions
        import werkzeug.routing.exceptions

        try:
            response = client.post("/holidays/99999/delete")
            assert response.status_code == 404
        except (werkzeug.exceptions.NotFound, werkzeug.routing.exceptions.BuildError):
            # Some configurations may raise these exceptions instead of returning
            # a 404 response object; treat them as equivalent to a 404 for this test.
            pass

    def test_delete_holiday_requires_admin(self, client, app):
        """Test that deleting holiday requires admin."""
        with app.app_context():
            holiday = Holiday(
                date=date(2030, 2, 1),
                name="Admin Test Holiday",
                is_federal=False,
            )
            db.session.add(holiday)
            db.session.commit()
            holiday_id = holiday.id

            original_user = os.environ.get("USER_NAME")
            original_admins = os.environ.get("ADMIN_USERS")
            try:
                os.environ["USER_NAME"] = "Regular User"
                os.environ["ADMIN_USERS"] = "Admin Only"

                response = client.post(
                    f"/holidays/{holiday_id}/delete",
                    follow_redirects=True,
                )
                assert b"Admin privileges required" in response.data
            finally:
                if original_user is not None:
                    os.environ["USER_NAME"] = original_user
                else:
                    os.environ.pop("USER_NAME", None)
                if original_admins is not None:
                    os.environ["ADMIN_USERS"] = original_admins
                else:
                    os.environ.pop("ADMIN_USERS", None)

            # Cleanup
            holiday = db.session.get(Holiday, holiday_id)
            if holiday:
                db.session.delete(holiday)
                db.session.commit()


class TestRefreshFederalHolidays:
    """Tests for refreshing federal holidays."""

    def test_refresh_federal_holidays(self, client, app):
        """Test refreshing federal holidays."""
        with app.app_context():
            response = client.post("/holidays/refresh", follow_redirects=True)
            assert response.status_code == 200
            # Should show success message about adding or already present
            assert b"Added" in response.data or b"already present" in response.data

    def test_refresh_federal_holidays_no_new(self, client, app):
        """Test refreshing when all holidays already exist."""
        with app.app_context():
            # First refresh to add all
            client.post("/holidays/refresh", follow_redirects=True)

            # Second refresh should show no new holidays
            response = client.post("/holidays/refresh", follow_redirects=True)
            assert response.status_code == 200
            assert b"already present" in response.data

    def test_refresh_federal_holidays_requires_admin(self, client):
        """Test that refreshing requires admin."""
        original_user = os.environ.get("USER_NAME")
        original_admins = os.environ.get("ADMIN_USERS")
        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.post("/holidays/refresh", follow_redirects=True)
            assert b"Admin privileges required" in response.data
        finally:
            if original_user is not None:
                os.environ["USER_NAME"] = original_user
            else:
                os.environ.pop("USER_NAME", None)
            if original_admins is not None:
                os.environ["ADMIN_USERS"] = original_admins
            else:
                os.environ.pop("ADMIN_USERS", None)

    def test_refresh_federal_holidays_adds_new(self, client, app):
        """Test refreshing when some holidays don't exist yet."""
        with app.app_context():
            # Delete all federal holidays first
            Holiday.query.filter_by(is_federal=True).delete()
            db.session.commit()

            response = client.post("/holidays/refresh", follow_redirects=True)
            assert response.status_code == 200
            # Should have "Added X" message
            assert b"Added" in response.data

            # Verify some federal holidays were added
            federal_count = Holiday.query.filter_by(is_federal=True).count()
            assert federal_count > 0


class TestHolidayExceptionHandling:
    """Tests for exception handling in holiday routes."""

    # noinspection DuplicatedCode
    def test_delete_holiday_db_error(self, client, app):
        """Test delete handles database errors gracefully."""
        with app.app_context():
            holiday = Holiday(
                date=date(2031, 1, 1),
                name="Error Test Holiday",
                is_federal=False,
            )
            db.session.add(holiday)
            db.session.commit()
            holiday_id = holiday.id

            # Mock commit to raise an exception
            with patch.object(db.session, "commit") as mock_commit:
                mock_commit.side_effect = Exception("Database error")

                response = client.post(
                    f"/holidays/{holiday_id}/delete",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"error" in response.data.lower()

            # Cleanup - rollback and delete
            db.session.rollback()
            holiday = db.session.get(Holiday, holiday_id)
            if holiday:
                db.session.delete(holiday)
                db.session.commit()

    def test_refresh_federal_holidays_db_error(self, client, app):
        """Test refresh handles database errors gracefully."""
        with app.app_context(), patch.object(db.session, "commit") as mock_commit:
            mock_commit.side_effect = Exception("Database error")

            response = client.post("/holidays/refresh", follow_redirects=True)
            assert response.status_code == 200
            assert b"error" in response.data.lower()
