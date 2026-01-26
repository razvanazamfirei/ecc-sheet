"""Extended tests for models."""

from datetime import date, time

import pytest

from backend.models import (
    AuditLog,
    Holiday,
    Role,
    TimeEntry,
    db,
)


class TestRoleModel:
    """Extended tests for Role model."""

    def test_role_is_backup_default(self, app):
        """Test that is_backup defaults to False."""
        with app.app_context():
            role = Role(name="Test Non-Backup", cutoff_hour=17, display_order=50)
            db.session.add(role)
            db.session.commit()

            assert role.is_backup is False

            db.session.delete(role)
            db.session.commit()

    def test_backup_role(self, app):
        """Test creating a backup role."""
        with app.app_context():
            role = Role(
                name="Test Backup Role",
                cutoff_hour=17,
                cutoff_minute=30,
                is_backup=True,
                display_order=51,
            )
            db.session.add(role)
            db.session.commit()

            assert role.is_backup is True

            db.session.delete(role)
            db.session.commit()


class TestTimeEntryModel:
    """Extended tests for TimeEntry model."""

    def test_overtime_with_start_time_on_weekend(self, app, sample_resident):
        """Test overtime calculation for backup role on weekend."""
        with app.app_context():
            # Create backup role
            backup_role = Role(
                name="Weekend Backup Test",
                cutoff_hour=17,
                cutoff_minute=30,
                is_backup=True,
                display_order=52,
            )
            db.session.add(backup_role)
            db.session.commit()

            # Create entry on a Saturday (Jan 6, 2024)
            saturday = date(2024, 1, 6)
            entry = TimeEntry(
                date=saturday,
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                start_time=time(9, 0),  # Called in at 9 AM
                exit_time=time(17, 0),  # Left at 5 PM
            )
            db.session.add(entry)
            db.session.commit()

            # All 8 hours should be overtime on weekend backup
            overtime = entry.calculate_overtime_hours()
            assert overtime == 8.0

            db.session.delete(entry)
            db.session.delete(backup_role)
            db.session.commit()

    def test_overtime_with_start_time_on_custom_holiday(self, app, sample_resident):
        """Test overtime calculation for backup role on custom holiday (not weekend)."""
        with app.app_context():
            # Create a custom holiday on a Tuesday (Jan 9, 2024)
            custom_holiday_date = date(2024, 1, 9)
            custom_holiday = Holiday(
                date=custom_holiday_date,
                name="Custom Hospital Holiday",
                is_federal=False,
            )
            db.session.add(custom_holiday)
            db.session.commit()

            # Create backup role
            backup_role = Role(
                name="Holiday Backup Test",
                cutoff_hour=17,
                cutoff_minute=30,
                is_backup=True,
                display_order=53,
            )
            db.session.add(backup_role)
            db.session.commit()

            # Create entry on custom holiday
            entry = TimeEntry(
                date=custom_holiday_date,
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                start_time=time(8, 0),  # Called in at 8 AM
                exit_time=time(16, 0),  # Left at 4 PM
            )
            db.session.add(entry)
            db.session.commit()

            # All 8 hours should be overtime on custom holiday backup
            overtime = entry.calculate_overtime_hours()
            assert overtime == 8.0

            db.session.delete(entry)
            db.session.delete(backup_role)
            db.session.delete(custom_holiday)
            db.session.commit()

    def test_overtime_backup_role_no_start_time_defaults_to_midnight(
        self, app, sample_resident
    ):
        """Test backup role on weekend without start_time defaults to midnight."""
        with app.app_context():
            # Create backup role
            backup_role = Role(
                name="No Start Backup Test",
                cutoff_hour=17,
                cutoff_minute=30,
                is_backup=True,
                display_order=54,
            )
            db.session.add(backup_role)
            db.session.commit()

            # Create entry on a Saturday (Jan 6, 2024) without start_time
            saturday = date(2024, 1, 6)
            entry = TimeEntry(
                date=saturday,
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                start_time=None,  # No start time set
                exit_time=time(17, 0),  # Left at 5 PM
            )
            db.session.add(entry)
            db.session.commit()

            # Should calculate from midnight (00:00) to 17:00 = 17 hours
            overtime = entry.calculate_overtime_hours()
            assert overtime == 17.0

            db.session.delete(entry)
            db.session.delete(backup_role)
            db.session.commit()

    def test_overtime_without_exit_time(self, app, sample_resident, sample_role):
        """Test overtime calculation without exit time returns 0."""
        with app.app_context():
            entry = TimeEntry(
                date=date.today(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.calculate_overtime_hours() == 0.0

            db.session.delete(entry)
            db.session.commit()

    def test_overtime_hours_property(self, app, sample_time_entry):
        """Test overtime_hours property."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            # Property should return same as method
            assert entry.overtime_hours == entry.calculate_overtime_hours()


class TestHolidayModel:
    """Extended tests for Holiday model."""

    def test_holiday_unique_date(self, app):
        """Test that holiday dates are unique."""
        with app.app_context():
            holiday1 = Holiday(
                date=date(2024, 12, 31),
                name="New Year's Eve",
                is_federal=False,
            )
            db.session.add(holiday1)
            db.session.commit()

            # Try to add another holiday on same date
            holiday2 = Holiday(
                date=date(2024, 12, 31),
                name="Duplicate",
                is_federal=False,
            )
            db.session.add(holiday2)

            with pytest.raises(Exception):
                db.session.commit()

            db.session.rollback()

            # Cleanup
            db.session.delete(holiday1)
            db.session.commit()


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, app):
        """Test creating an audit log entry."""
        with app.app_context():
            from datetime import UTC, datetime

            log = AuditLog(
                timestamp=datetime.now(UTC),
                user="TestUser",
                action="TEST",
                entity_type="TestEntity",
                entity_id=1,
                details='{"test": "data"}',
                ip_address="127.0.0.1",
            )
            db.session.add(log)
            db.session.commit()

            assert log.id is not None

            db.session.delete(log)
            db.session.commit()
