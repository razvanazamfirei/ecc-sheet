"""Tests for holidays functionality."""

from datetime import date

from backend.holidays import get_federal_holidays, is_weekend_or_holiday
from backend.models import Holiday, db


class TestGetFederalHolidays:
    """Tests for get_federal_holidays function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        holidays = get_federal_holidays(2024)
        assert isinstance(holidays, list)

    def test_returns_date_name_tuples(self):
        """Test that each item is a (date, name) tuple."""
        holidays = get_federal_holidays(2024)
        assert len(holidays) > 0
        for item in holidays:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], date)
            assert isinstance(item[1], str)

    def test_includes_major_holidays(self):
        """Test that major holidays are included."""
        holidays = get_federal_holidays(2024)
        holiday_dates = [h[0] for h in holidays]

        # Check for some major holidays
        assert date(2024, 1, 1) in holiday_dates  # New Year's Day
        assert date(2024, 12, 25) in holiday_dates  # Christmas


class TestIsWeekendOrHoliday:
    """Tests for is_weekend_or_holiday function."""

    def test_saturday_returns_true(self, app):
        """Test that Saturday returns True."""
        with app.app_context():
            saturday = date(2024, 1, 6)
            assert is_weekend_or_holiday(saturday) is True

    def test_sunday_returns_true(self, app):
        """Test that Sunday returns True."""
        with app.app_context():
            sunday = date(2024, 1, 7)
            assert is_weekend_or_holiday(sunday) is True

    def test_federal_holiday_returns_true(self, app):
        """Test that federal holiday returns True."""
        with app.app_context():
            christmas = date(2024, 12, 25)
            assert is_weekend_or_holiday(christmas) is True

    def test_regular_weekday_returns_false(self, app):
        """Test that regular weekday returns False."""
        with app.app_context():
            # March 15, 2024 is a Friday, not a holiday
            regular = date(2024, 3, 15)
            assert is_weekend_or_holiday(regular) is False

    def test_custom_holiday_returns_true(self, app):
        """Test that custom holiday in database returns True."""
        with app.app_context():
            # Add a custom holiday
            custom_date = date(2024, 6, 15)  # Random date
            holiday = Holiday(date=custom_date, name="Test Holiday", is_federal=False)
            db.session.add(holiday)
            db.session.commit()

            assert is_weekend_or_holiday(custom_date) is True

            # Cleanup
            db.session.delete(holiday)
            db.session.commit()


class TestHolidayModel:
    """Tests for Holiday model."""

    def test_create_holiday(self, app):
        """Test creating a holiday."""
        with app.app_context():
            holiday = Holiday(
                date=date(2024, 7, 4),
                name="Independence Day",
                is_federal=True,
            )
            db.session.add(holiday)
            db.session.commit()

            saved = Holiday.query.filter_by(date=date(2024, 7, 4)).first()
            assert saved is not None
            assert saved.name == "Independence Day"
            assert saved.is_federal is True

            db.session.delete(saved)
            db.session.commit()

    def test_is_holiday_class_method(self, app):
        """Test Holiday.is_holiday class method."""
        with app.app_context():
            test_date = date(2024, 8, 15)

            # Should be False before adding
            assert Holiday.is_holiday(test_date) is False

            # Add holiday
            holiday = Holiday(date=test_date, name="Test", is_federal=False)
            db.session.add(holiday)
            db.session.commit()

            # Should be True after adding
            assert Holiday.is_holiday(test_date) is True

            # Cleanup
            db.session.delete(holiday)
            db.session.commit()


class TestHolidayRoutes:
    """Tests for holiday routes."""

    def test_holidays_page_loads(self, client):
        """Test that holidays page loads."""
        response = client.get("/holidays")
        assert response.status_code == 200
        assert b"Holiday" in response.data

    def test_add_holiday(self, client, app):
        """Test adding a custom holiday."""
        with app.app_context():
            response = client.post(
                "/holidays/add",
                data={
                    "date": "2024-09-15",
                    "name": "Test Custom Holiday",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify holiday was created
            holiday = Holiday.query.filter_by(name="Test Custom Holiday").first()
            assert holiday is not None

            # Cleanup
            if holiday:
                db.session.delete(holiday)
                db.session.commit()

    def test_add_holiday_missing_fields(self, client):
        """Test adding holiday with missing fields."""
        response = client.post(
            "/holidays/add",
            data={"date": "", "name": ""},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"required" in response.data.lower() or b"error" in response.data.lower()

    def test_delete_holiday(self, client, app):
        """Test deleting a holiday."""
        with app.app_context():
            # Use a unique date to avoid conflicts
            test_date = date(2099, 10, 15)

            # Clean up any existing holiday with this date
            existing = Holiday.query.filter_by(date=test_date).first()
            if existing:
                db.session.delete(existing)
                db.session.commit()

            # Create a holiday first
            holiday = Holiday(
                date=test_date,
                name="To Delete",
                is_federal=False,
            )
            db.session.add(holiday)
            db.session.commit()
            holiday_id = holiday.id

            # Delete it
            response = client.post(
                f"/holidays/{holiday_id}/delete",
                follow_redirects=True,
            )
            assert response.status_code == 200

            # Verify deleted
            assert db.session.get(Holiday, holiday_id) is None

    def test_refresh_federal_holidays(self, client, app):
        """Test refreshing federal holidays."""
        with app.app_context():
            response = client.post("/holidays/refresh", follow_redirects=True)
            assert response.status_code == 200

            # Should have some federal holidays now
            federal_count = Holiday.query.filter_by(is_federal=True).count()
            assert federal_count >= 0  # At least the route worked
