"""
Tests for utility functions
"""

import pathlib
from datetime import date, datetime, time, timedelta

import pytest
import pytz

from backend.config import Config
from backend.utils import (
    get_effective_date,
    get_philadelphia_time,
    philly_today,
    round_to_quarter_hour,
)


@pytest.mark.timezone
class TestPhiladelphiaTime:
    """Test Philadelphia timezone utilities"""

    def test_get_philadelphia_time_returns_aware_datetime(self):
        """Test that get_philadelphia_time returns timezone-aware datetime"""
        philly_time = get_philadelphia_time()
        assert philly_time.tzinfo is not None
        assert philly_time.tzinfo.zone == "America/New_York"

    def test_get_philadelphia_time_is_current(self):
        """Test that returned time is reasonably current"""
        philly_time = get_philadelphia_time()
        now = datetime.now()

        # Should be within a few seconds of now
        time_diff = abs((philly_time.replace(tzinfo=None) - now).total_seconds())
        assert time_diff < 10  # Within 10 seconds


@pytest.mark.timezone
class TestEffectiveDate:
    """Test effective date calculation with 8 AM reset"""

    def test_effective_date_after_8am(self):
        """Test that times after 8 AM belong to current calendar day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 10:00 AM today
        test_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_before_8am(self):
        """Test that times before 8 AM belong to previous calendar day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 6:00 AM today
        test_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_exactly_8am(self):
        """Test that exactly 8:00 AM belongs to current day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Exactly 8:00 AM today
        test_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_just_before_8am(self):
        """Test that 7:59 AM belongs to previous day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 7:59 AM today
        test_time = datetime.now().replace(hour=7, minute=59, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_midnight(self):
        """Test that midnight belongs to previous day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Midnight today
        test_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_late_night(self):
        """Test that late night (11 PM) belongs to current day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 11:00 PM today
        test_time = datetime.now().replace(hour=23, minute=0, second=0, microsecond=0)
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_default_uses_current_time(self):
        """Test that calling without argument uses current time"""
        effective = get_effective_date()
        assert isinstance(effective, date)

    def test_effective_date_handles_naive_datetime(self):
        """Test that naive datetimes are properly localized"""
        # Create naive datetime
        naive_time = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)

        effective = get_effective_date(naive_time)
        assert isinstance(effective, date)


@pytest.mark.timezone
class TestPhillyToday:
    """Test philly_today function"""

    def test_philly_today_returns_date(self):
        """Test that philly_today returns a date object"""
        today = philly_today()
        assert isinstance(today, date)

    def test_philly_today_accounts_for_8am_reset(self):
        """Test that philly_today uses effective date logic"""
        # This test would need to be run at specific times to fully verify
        # For now, just ensure it returns a valid date
        today = philly_today()
        assert isinstance(today, date)

        # Should be within a reasonable range
        actual_today = date.today()
        yesterday = actual_today - timedelta(days=1)

        # philly_today should be either yesterday or today depending on time
        assert today in {yesterday, actual_today}


@pytest.mark.unit
class TestTimeValidation:
    """Test time format validation"""

    def test_validate_time_format_valid(self):
        """Test validation of valid time formats"""
        from backend.utils import validate_time_format

        valid_times = [
            "00:00",
            "08:30",
            "12:00",
            "17:30",
            "23:59",
        ]

        for time_str in valid_times:
            assert validate_time_format(time_str) is True, f"Failed for {time_str}"

    def test_validate_time_format_invalid(self):
        """Test validation of invalid time formats"""
        from backend.utils import validate_time_format

        invalid_times = [
            "25:00",  # Invalid hour
            "12:60",  # Invalid minute
            "noon",  # Not a time
            "",  # Empty string
            None,  # None
            "12:",  # Missing minutes
            ":30",  # Missing hour
        ]

        for time_str in invalid_times:
            assert validate_time_format(time_str) is False, f"Failed for {time_str}"

    def test_validate_time_format_accepts_lenient(self):
        """Test that validation accepts lenient formats (Python's strptime behavior)"""
        from backend.utils import validate_time_format

        # These are accepted by Python's strptime even without leading zeros
        lenient_times = [
            "1:30",  # Single digit hour
            "12:5",  # Single digit minute
        ]

        for time_str in lenient_times:
            assert validate_time_format(time_str) is True, f"Failed for {time_str}"


@pytest.mark.unit
class TestSanitizeString:
    """Test string sanitization"""

    def test_sanitize_string_normal(self):
        """Test sanitizing normal strings"""
        from backend.utils import sanitize_string

        assert sanitize_string("  Hello World  ") == "Hello World"
        assert sanitize_string("Test Name") == "Test Name"

    def test_sanitize_string_max_length(self):
        """Test max length enforcement"""
        from backend.utils import sanitize_string

        long_string = "a" * 200
        result = sanitize_string(long_string, max_length=50)
        assert len(result) == 50

    def test_sanitize_string_removes_control_chars(self):
        """Test that control characters are removed"""
        from backend.utils import sanitize_string

        # String with newlines and tabs
        result = sanitize_string("Hello\nWorld\t!")
        assert "\n" not in result
        assert "\t" not in result

    def test_sanitize_string_empty(self):
        """Test sanitizing empty strings"""
        from backend.utils import sanitize_string

        assert not sanitize_string("")
        assert not sanitize_string(None)


@pytest.mark.unit
class TestRoundToQuarterHour:
    """Test rounding to 15-minute increments"""

    def test_round_to_nearest_quarter(self):
        """Test rounding to nearest 15 minutes"""
        test_cases = [
            (time(10, 0), time(10, 0)),  # Already on quarter hour
            (time(10, 7), time(10, 0)),  # Round down
            (time(10, 8), time(10, 15)),  # Round up
            (time(10, 15), time(10, 15)),  # Already on quarter hour
            (time(10, 22), time(10, 15)),  # Round down
            (time(10, 23), time(10, 30)),  # Round up
            (time(10, 30), time(10, 30)),  # Already on quarter hour
            (time(10, 37), time(10, 30)),  # Round down
            (time(10, 38), time(10, 45)),  # Round up
            (time(10, 45), time(10, 45)),  # Already on quarter hour
            (time(10, 52), time(10, 45)),  # Round down
            (time(10, 53), time(11, 0)),  # Round up to next hour
        ]

        for input_time, expected in test_cases:
            result = round_to_quarter_hour(input_time)
            assert result == expected, (
                f"Failed for {input_time}: got {result}, expected {expected}"
            )

    def test_round_hour_rollover(self):
        """Test rounding that rolls over to next hour"""
        assert round_to_quarter_hour(time(9, 53)) == time(10, 0)
        assert round_to_quarter_hour(time(23, 53)) == time(0, 0)

    def test_round_midnight(self):
        """Test rounding around midnight"""
        assert round_to_quarter_hour(time(23, 52)) == time(23, 45)
        assert round_to_quarter_hour(time(23, 53)) == time(0, 0)
        assert round_to_quarter_hour(time(0, 7)) == time(0, 0)
        assert round_to_quarter_hour(time(0, 8)) == time(0, 15)


@pytest.mark.unit
class TestBackupDatabase:
    """Test database backup functionality"""

    def test_backup_database_creates_file(self, app, tmp_path):
        """Test that backup creates a file"""

        from backend.utils import backup_database

        with app.app_context():
            # Use temp directory for backups
            backup_dir = str(tmp_path / "backups")
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            # Create backup
            result = backup_database(db_path, backup_dir)
            assert result is True

            # Verify backup file exists
            assert pathlib.Path(backup_dir).exists()
            backups = list(pathlib.Path(backup_dir).iterdir())
            assert len(backups) > 0
            assert backups[0].name.endswith(".db")

    def test_backup_database_nonexistent_file(self, tmp_path):
        """Test backup of non-existent database"""
        from backend.utils import backup_database

        result = backup_database("nonexistent.db", str(tmp_path))
        assert result is False


@pytest.mark.timezone
class TestTimezoneEdgeCases:
    """Test timezone-related edge cases"""

    def test_daylight_saving_time_transition(self):
        """Test behavior around DST transitions"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Spring forward: 2 AM -> 3 AM (second Sunday in March)
        # Fall back: 2 AM -> 1 AM (first Sunday in November)

        # Test date in EDT (summer)
        summer_time = philly_tz.localize(datetime(2024, 7, 1, 12, 0, 0))
        assert summer_time.tzinfo is not None

        # Test date in EST (winter)
        winter_time = philly_tz.localize(datetime(2024, 1, 1, 12, 0, 0))
        assert winter_time.tzinfo is not None

    def test_effective_date_across_dst_boundary(self):
        """Test effective date calculation across DST boundary"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Early morning during DST transition
        # This test ensures the 8 AM logic works regardless of DST
        test_time = datetime(2024, 3, 10, 7, 0, 0)  # DST transition day
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected


@pytest.mark.unit
class TestPhillyNow:
    """Test philly_now convenience function"""

    def test_philly_now_returns_aware_datetime(self):
        """Test that philly_now returns timezone-aware datetime"""
        from backend.utils import philly_now

        now = philly_now()
        assert now.tzinfo is not None
        assert now.tzinfo.zone == "America/New_York"

    def test_philly_now_equivalent_to_get_philadelphia_time(self):
        """Test that philly_now is equivalent to get_philadelphia_time"""
        from backend.utils import philly_now

        result = philly_now()
        expected = get_philadelphia_time()

        # Should be within 1 second of each other
        time_diff = abs((result - expected).total_seconds())
        assert time_diff < 1
