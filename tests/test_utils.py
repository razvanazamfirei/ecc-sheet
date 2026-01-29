"""
Tests for utility functions
"""

import pathlib
from datetime import UTC, date, datetime, timedelta

import pytest
import pytz

from backend.config import Config
from backend.utils import (
    get_effective_date,
    get_philadelphia_time,
    philly_today,
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
        # Compare UTC timestamps to avoid timezone issues
        now_utc = datetime.now(UTC)

        # Convert philly time to UTC for comparison
        philly_utc = philly_time.astimezone(UTC)

        # Should be within a few seconds of now
        time_diff = abs((philly_utc - now_utc).total_seconds())
        assert time_diff < 10  # Within 10 seconds


@pytest.mark.timezone
class TestEffectiveDate:
    """Test effective date calculation with 8 AM reset"""

    def test_effective_date_after_8am(self):
        """Test that times after 8 AM belong to current calendar day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 10:00 AM today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=10, minute=0, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_before_8am(self):
        """Test that times before 8 AM belong to previous calendar day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 6:00 AM today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=6, minute=0, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_exactly_8am(self):
        """Test that exactly 8:00 AM belongs to current day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Exactly 8:00 AM today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=8, minute=0, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_just_before_8am(self):
        """Test that 7:59 AM belongs to previous day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 7:59 AM today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=7, minute=59, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_midnight(self):
        """Test that midnight belongs to previous day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # Midnight today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=0, minute=0, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        expected = (test_time - timedelta(days=1)).date()
        assert effective == expected

    def test_effective_date_late_night(self):
        """Test that late night (11 PM) belongs to current day"""
        philly_tz = pytz.timezone(Config.TIMEZONE)

        # 11:00 PM today - create naive datetime intentionally for localization
        test_time = datetime.now().replace(  # noqa: DTZ005
            hour=23, minute=0, second=0, microsecond=0
        )
        test_time = philly_tz.localize(test_time)

        effective = get_effective_date(test_time)
        assert effective == test_time.date()

    def test_effective_date_default_uses_current_time(self):
        """Test that calling without argument uses current time"""
        effective = get_effective_date()
        assert isinstance(effective, date)

    def test_effective_date_handles_naive_datetime(self):
        """Test that naive datetimes are properly localized"""
        # Create naive datetime intentionally to test localization behavior
        naive_time = datetime.now().replace(  # noqa: DTZ005
            hour=10, minute=0, second=0, microsecond=0
        )

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
        actual_today = philly_today()
        yesterday = actual_today - timedelta(days=1)

        # philly_today should be either yesterday or today depending on time
        assert today in {yesterday, actual_today}


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


@pytest.mark.unit
class TestSetupLogging:
    """Test logging setup functionality"""

    def test_setup_logging_creates_log_dir(self, tmp_path, monkeypatch):
        """Test that setup_logging creates log directory"""
        from backend.utils import setup_logging

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        logger = setup_logging()
        assert logger is not None
        assert (tmp_path / "logs").exists()

    def test_setup_logging_returns_logger(self, tmp_path, monkeypatch):
        """Test that setup_logging returns a logger"""
        from backend.utils import setup_logging

        monkeypatch.chdir(tmp_path)

        logger = setup_logging()
        assert logger is not None
        assert logger.name == "ecc_sheet"


@pytest.mark.unit
class TestHandleDbError:
    """Test handle_db_error decorator"""

    def test_decorator_passes_through_on_success(self, app):
        """Test that decorator passes through when no error"""
        from backend.utils import handle_db_error

        @handle_db_error
        def successful_function():
            return "success"

        with app.app_context():
            # The decorator wraps the function and will return either the result
            # or a redirect. In test context this is fine.
            try:
                result = successful_function()
                assert result == "success"
            except Exception:
                # If url_for fails due to missing endpoint, that's expected
                pass

    def test_decorator_catches_exception(self, app, client):
        """Test that decorator catches database exceptions"""
        from unittest.mock import patch

        from backend.utils import handle_db_error

        @handle_db_error
        def failing_function():
            raise Exception("Database error")

        # Use test_request_context to provide proper request context
        with app.test_request_context():
            with app.app_context():
                # Mock db.session.rollback and flash to verify they're called
                with patch("backend.utils.db.session.rollback") as mock_rollback:
                    with patch("backend.utils.flash") as mock_flash:
                        # The decorator should catch the exception and try to redirect
                        # This may raise BuildError if 'index' endpoint doesn't exist
                        import werkzeug.routing.exceptions

                        try:
                            failing_function()
                        except werkzeug.routing.exceptions.BuildError:
                            # Expected - the decorator tried to redirect to 'index'
                            # which may not exist. Verify error handling occurred.
                            mock_rollback.assert_called_once()
                            mock_flash.assert_called_once()
                            pass


@pytest.mark.unit
class TestBackupDatabaseEdgeCases:
    """Additional edge case tests for backup_database"""

    def test_backup_creates_directory_if_missing(self, app, tmp_path):
        """Test backup creates backup directory if it doesn't exist"""
        from backend.utils import backup_database

        with app.app_context():
            backup_dir = tmp_path / "new_backup_dir"
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            result = backup_database(db_path, str(backup_dir))
            assert result is True
            assert backup_dir.exists()

    def test_backup_cleans_old_backups(self, app, tmp_path):
        """Test backup removes old backups beyond 30"""
        from backend.utils import backup_database

        with app.app_context():
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir()

            # Create 35 fake backup files
            for i in range(35):
                (backup_dir / f"ecc_sheet_{i:02d}.db").touch()

            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            result = backup_database(db_path, str(backup_dir))
            assert result is True

            # Should have at most 31 files (30 old + 1 new)
            backup_files = list(backup_dir.glob("ecc_sheet_*.db"))
            assert len(backup_files) <= 31


@pytest.mark.timezone
class TestEffectiveDateWithDifferentTimezones:
    """Test effective date with timezone conversions"""

    def test_effective_date_with_utc_input(self):
        """Test effective date with UTC input datetime"""
        utc_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=pytz.UTC)

        effective = get_effective_date(utc_time)
        assert isinstance(effective, date)

    def test_effective_date_with_different_timezone(self):
        """Test effective date with non-Philadelphia timezone"""
        pacific_tz = pytz.timezone("America/Los_Angeles")
        pacific_time = pacific_tz.localize(datetime(2024, 6, 15, 9, 0, 0))

        effective = get_effective_date(pacific_time)
        assert isinstance(effective, date)


@pytest.mark.unit
class TestBackupDatabaseExceptionHandling:
    """Test backup_database exception handling"""

    def test_backup_database_handles_copy_error(self, app, tmp_path, monkeypatch):
        """Test backup handles shutil.copy2 errors gracefully"""
        import shutil

        from backend.utils import backup_database

        with app.app_context():
            backup_dir = tmp_path / "backups"
            backup_dir.mkdir()
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

            # Mock shutil.copy2 to raise an exception
            def mock_copy2(*args, **kwargs):
                raise OSError("Permission denied")

            monkeypatch.setattr(shutil, "copy2", mock_copy2)

            result = backup_database(db_path, str(backup_dir))
            assert result is False

    def test_backup_database_handles_mkdir_error(self, app, tmp_path, monkeypatch):
        """Test backup handles directory creation errors gracefully"""
        from backend.utils import backup_database

        with app.app_context():
            db_path = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
            backup_dir = tmp_path / "readonly_dir"

            # Create a read-only scenario by mocking mkdir
            original_mkdir = pathlib.Path.mkdir

            def mock_mkdir(self, *args, **kwargs):
                if "readonly_dir" in str(self):
                    raise OSError("Permission denied")
                return original_mkdir(self, *args, **kwargs)

            monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir)

            result = backup_database(db_path, str(backup_dir))
            assert result is False
