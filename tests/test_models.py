"""
Tests for database models
"""

from datetime import UTC, date, datetime, time
from math import isclose

import pytest

from backend.app import db
from backend.models import DailySheet, Resident, Role, TimeEntry
from backend.utils import get_effective_date


@pytest.mark.unit
class TestRole:
    """Test Role model"""

    def test_role_creation(self, app):
        """Test creating a role"""
        with app.app_context():
            # Use unique name to avoid conflicts
            role = Role(
                name="Test Role Creation",
                cutoff_hour=18,
                cutoff_minute=0,
                display_order=1,
            )
            db.session.add(role)
            db.session.commit()

            assert role.id is not None
            assert role.name == "Test Role Creation"
            assert role.cutoff_hour == 18
            assert role.cutoff_minute == 0
            assert role.display_order == 1

            # Cleanup
            db.session.delete(role)
            db.session.commit()

    def test_cutoff_time_str(self, sample_role):
        """Test cutoff_time_str property"""
        assert sample_role.cutoff_time_str == "17:30"

    def test_cutoff_time_str_formats(self, app):
        """Test various cutoff time formats"""
        with app.app_context():
            # Test midnight
            role1 = Role(
                name="Midnight", cutoff_hour=0, cutoff_minute=0, display_order=1
            )
            assert role1.cutoff_time_str == "00:00"

            # Test single digit minutes
            role2 = Role(name="Single", cutoff_hour=9, cutoff_minute=5, display_order=2)
            assert role2.cutoff_time_str == "09:05"

            # Test 23:59
            role3 = Role(name="Late", cutoff_hour=23, cutoff_minute=59, display_order=3)
            assert role3.cutoff_time_str == "23:59"


@pytest.mark.unit
class TestResident:
    """Test Resident model"""

    def test_resident_creation(self, app):
        """Test creating a resident"""
        with app.app_context():
            resident = Resident(name="Dr. Test", active=True)
            db.session.add(resident)
            db.session.commit()

            assert resident.id is not None
            assert resident.name == "Dr. Test"
            assert resident.active is True

    def test_resident_active_by_default(self, app):
        """Test that residents are active by default"""
        with app.app_context():
            resident = Resident(name="Dr. Default")
            db.session.add(resident)
            db.session.commit()

            assert resident.active is True

    def test_resident_deactivation(self, sample_resident):
        """Test deactivating a resident"""
        sample_resident.active = False
        db.session.commit()

        assert sample_resident.active is False

    def test_class_year_valid_values_accepted(self, app):
        """Test that valid class_year values are stored."""
        with app.app_context():
            for cy in Resident.CLASS_YEARS:
                resident = Resident(name=f"CY Valid {cy}", class_year=cy)
                db.session.add(resident)
                db.session.commit()
                assert resident.class_year == cy
                db.session.delete(resident)
                db.session.commit()

    def test_class_year_invalid_value_cleared_to_none(self, app):
        """Test that invalid class_year values are set to None by the validator."""
        with app.app_context():
            resident = Resident(name="CY Invalid Test", class_year="CA1")
            db.session.add(resident)
            db.session.commit()
            assert resident.class_year is None
            db.session.delete(resident)
            db.session.commit()

    def test_class_year_none_is_accepted(self, app):
        """Test that None class_year is stored as-is."""
        with app.app_context():
            resident = Resident(name="CY None Test", class_year=None)
            db.session.add(resident)
            db.session.commit()
            assert resident.class_year is None
            db.session.delete(resident)
            db.session.commit()

    def test_resident_new_fields_storage(self, app):
        """Test that first_name, last_name, lawson_id, and hire_date are persisted."""
        with app.app_context():
            resident = Resident(
                name="Fields Storage Test",
                first_name="Alice",
                last_name="Smith",
                lawson_id=12345,
                hire_date=date(2023, 7, 1),
            )
            db.session.add(resident)
            db.session.commit()

            fetched = db.session.get(Resident, resident.id)
            assert fetched is not None
            assert fetched.first_name == "Alice"
            assert fetched.last_name == "Smith"
            assert fetched.lawson_id == 12345
            assert fetched.hire_date == date(2023, 7, 1)

            db.session.delete(fetched)
            db.session.commit()

    def test_resident_new_fields_nullable(self, app):
        """Test that first_name, last_name, lawson_id, and hire_date default to None."""
        with app.app_context():
            resident = Resident(name="Fields Nullable Test")
            db.session.add(resident)
            db.session.commit()

            fetched = db.session.get(Resident, resident.id)
            assert fetched is not None
            assert fetched.first_name is None
            assert fetched.last_name is None
            assert fetched.lawson_id is None
            assert fetched.hire_date is None

            db.session.delete(fetched)
            db.session.commit()

    def test_class_years_constant_contains_expected_values(self):
        """Test that CLASS_YEARS contains the expected canonical values."""
        assert "CA-1" in Resident.CLASS_YEARS
        assert "CA-2" in Resident.CLASS_YEARS
        assert "CA-3" in Resident.CLASS_YEARS
        assert "Fellow" in Resident.CLASS_YEARS
        assert "OMFS" in Resident.CLASS_YEARS
        assert "CA1" not in Resident.CLASS_YEARS


@pytest.mark.overtime
class TestOvertimeCalculation:
    """Test overtime calculation logic"""

    def test_same_day_overtime(self, app, sample_resident, sample_role):
        """Test overtime for same-day exit (after cutoff)"""
        with app.app_context():
            # Exit at 20:00, cutoff at 17:30 → 2.5 hours overtime
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 2.5, abs_tol=0.01)

    def test_overnight_overtime(self, app, sample_resident, sample_role):
        """Test overtime for overnight shift (AM exit time)"""
        with app.app_context():
            # Exit at 02:30 AM, cutoff at 17:30 → 9 hours overnight
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(2, 30),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 9.0, abs_tol=0.01)

    def test_midnight_overtime(self, app, sample_resident, sample_role):
        """Test overtime for midnight exit"""
        with app.app_context():
            # Exit at 00:00, cutoff at 17:30 → 6.5 hours
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(0, 0),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 6.5, abs_tol=0.01)

    def test_no_overtime_at_cutoff(self, app, sample_resident, sample_role):
        """Test no overtime when exiting exactly at cutoff"""
        with app.app_context():
            # Exit at 17:30, cutoff at 17:30 → 0 hours
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(17, 30),
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.overtime_hours == 0

    def test_no_overtime_before_cutoff(self, app, sample_resident, sample_role):
        """Test no overtime for afternoon exit before cutoff"""
        with app.app_context():
            # Exit at 15:00, cutoff at 17:30 → 0 hours (not overnight)
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(15, 0),
            )
            db.session.add(entry)
            db.session.commit()

            # Before cutoff and not in AM hours, so treated as early departure
            # Exit time 15:00 is after overnight threshold (8:00), so no overtime
            assert entry.overtime_hours == 0

    def test_late_night_overtime(self, app, sample_resident, sample_role):
        """Test overtime for late night (before midnight)"""
        with app.app_context():
            # Exit at 23:45, cutoff at 17:30 → 6.25 hours
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(23, 45),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 6.25, abs_tol=0.01)

    def test_early_morning_overtime(self, app, sample_resident, sample_role):
        """Test overtime for early morning (around 7 AM)"""
        with app.app_context():
            # Exit at 07:00 AM, cutoff at 17:30 → 13.5 hours overnight
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(7, 0),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 13.5, abs_tol=0.01)

    def test_different_cutoff_time(self, app, sample_resident):
        """Test overtime with different cutoff time"""
        with app.app_context():
            # Create role with 20:00 cutoff using unique name
            role = Role(
                name="Late Shift Test",
                cutoff_hour=20,
                cutoff_minute=0,
                display_order=200,
            )
            db.session.add(role)
            db.session.commit()

            # Exit at 22:30, cutoff at 20:00 → 2.5 hours
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=role.id,
                exit_time=time(22, 30),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 2.5, abs_tol=0.01)

            # Cleanup
            db.session.delete(entry)
            db.session.delete(role)
            db.session.commit()

    def test_fifteen_minute_increments(self, app, sample_resident, sample_role):
        """Test overtime calculation with 5-minute increments"""
        with app.app_context():
            # Exit at 18:15, cutoff at 17:30 → 0.75 hours (45 minutes)
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(18, 15),
            )
            db.session.add(entry)
            db.session.commit()

            assert isclose(entry.overtime_hours, 0.75, abs_tol=0.01)

    def test_call_team_role_returns_zero_overtime(self, app, sample_resident):
        """Test that is_call_team roles always return 0.0 overtime hours."""
        with app.app_context():
            role = Role(
                name="Call Team OT Test",
                cutoff_hour=17,
                cutoff_minute=30,
                is_call_team=True,
                display_order=200,
            )
            db.session.add(role)
            db.session.commit()

            # Even with an exit time well after cutoff, overtime must be 0
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=role.id,
                exit_time=time(22, 0),
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.overtime_hours == 0

            db.session.delete(entry)
            db.session.delete(role)
            db.session.commit()


@pytest.mark.unit
class TestTimeEntry:
    """Test TimeEntry model"""

    def test_time_entry_creation(self, app, sample_resident, sample_role):
        """Test creating a time entry"""
        with app.app_context():
            today = get_effective_date()
            entry = TimeEntry(
                date=today,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(20, 0),
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.id is not None
            assert entry.date == today
            assert entry.resident_id == sample_resident.id
            assert entry.role_id == sample_role.id
            assert entry.exit_time == time(20, 0)

    def test_time_entry_relationships(self, sample_time_entry):
        """Test TimeEntry relationships with Resident and Role"""
        assert sample_time_entry.resident is not None
        assert sample_time_entry.role is not None
        assert sample_time_entry.resident.name == "Test Resident"
        assert sample_time_entry.role.name == "Test Role"

    def test_time_entry_nullable_exit_time(self, app, sample_resident, sample_role):
        """Test that exit_time can be null"""
        with app.app_context():
            entry = TimeEntry(
                date=get_effective_date(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=None,  # No exit time yet
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.exit_time is None
            assert entry.overtime_hours == 0


@pytest.mark.unit
class TestDailySheet:
    """Test DailySheet model"""

    def test_daily_sheet_creation(self, app):
        """Test creating a daily sheet"""
        from datetime import timedelta

        with app.app_context():
            # Use a future date to avoid conflicts
            test_date = get_effective_date() + timedelta(days=10)
            sheet = DailySheet(date=test_date, locked=False, submitted=False)
            db.session.add(sheet)
            db.session.commit()

            assert sheet.id is not None
            assert sheet.date == test_date
            assert sheet.locked is False
            assert sheet.submitted is False
            assert sheet.submitted_at is None

            # Cleanup
            db.session.delete(sheet)
            db.session.commit()

    def test_daily_sheet_locking(self, sample_daily_sheet):
        """Test locking a daily sheet"""
        sample_daily_sheet.locked = True
        db.session.commit()

        assert sample_daily_sheet.locked is True

    def test_daily_sheet_submission(self, app):
        """Test submitting a daily sheet"""
        with app.app_context():
            # Use a date far in the future to avoid conflicts with fixtures
            test_date = date(2099, 1, 1)
            sheet = DailySheet(
                date=test_date,
                locked=True,
                submitted=True,
                submitted_at=datetime.now(UTC),
            )
            db.session.add(sheet)
            db.session.commit()

            assert sheet.submitted is True
            assert sheet.submitted_at is not None

            # Clean up
            db.session.delete(sheet)
            db.session.commit()

    def test_daily_sheet_unique_date(self, app, sample_daily_sheet):
        """Test that daily sheets have unique dates"""
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            # Try to create another sheet for the same date
            duplicate = DailySheet(
                date=sample_daily_sheet.date, locked=False, submitted=False
            )
            db.session.add(duplicate)

            # This should raise an IntegrityError due to unique constraint
            with pytest.raises(IntegrityError):
                db.session.commit()
