"""Extended tests for models."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.models import (
    AuditLog,
    DailySheet,
    Holiday,
    Resident,
    Role,
    TimeEntry,
    db,
)
from backend.utils import philly_today


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

    def test_role_repr(self, app):
        """Test Role __repr__ method."""
        with app.app_context():
            role = Role(name="Repr Test Role", cutoff_hour=17, display_order=55)
            assert repr(role) == "<Role Repr Test Role>"


class TestResidentModel:
    """Extended tests for Resident model."""

    def test_display_name(self, app):
        """Test display_name property."""
        with app.app_context():
            resident = Resident(name="John Doe", active=True)
            assert resident.display_name == "John Doe"

    def test_status_active(self, app):
        """Test status property for active resident."""
        with app.app_context():
            resident = Resident(name="Active Person", active=True)
            assert resident.status == "Active"

    def test_status_inactive(self, app):
        """Test status property for inactive resident."""
        with app.app_context():
            resident = Resident(name="Inactive Person", active=False)
            assert resident.status == "Inactive"

    def test_total_entries(self, app):
        """Test total_entries property."""
        with app.app_context():
            resident = Resident(name="Entry Count Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(name="Entry Count Role", cutoff_hour=17, display_order=60)
            db.session.add(role)
            db.session.commit()

            # Create some entries
            for i in range(3):
                entry = TimeEntry(
                    date=philly_today() + timedelta(days=i + 100),
                    resident_id=resident.id,
                    role_id=role.id,
                    exit_time=time(18, 0),
                )
                db.session.add(entry)
            db.session.commit()

            assert resident.total_entries == 3

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_active_entries(self, app):
        """Test active_entries property (entries not submitted)."""
        with app.app_context():
            resident = Resident(name="Active Entry Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(name="Active Entry Role", cutoff_hour=17, display_order=61)
            db.session.add(role)
            db.session.commit()

            # Create submitted and non-submitted entries
            entry1 = TimeEntry(
                date=philly_today() + timedelta(days=200),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
                submitted=True,
            )
            entry2 = TimeEntry(
                date=philly_today() + timedelta(days=201),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
                submitted=False,
            )
            entry3 = TimeEntry(
                date=philly_today() + timedelta(days=202),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
                submitted=False,
            )
            db.session.add_all([entry1, entry2, entry3])
            db.session.commit()

            active = resident.active_entries
            assert len(active) == 2
            assert all(not e.submitted for e in active)

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_to_dict_basic(self, app):
        """Test to_dict method without entries."""
        with app.app_context():
            resident = Resident(
                name="Dict Test",
                epic_id="EPIC123",
                active=True,
                class_year="CA2",
                email="test@example.com",
                phone="555-1234",
                abbreviation="DT",
                backup_id="B123",
            )
            db.session.add(resident)
            db.session.commit()

            data = resident.to_dict()

            assert data["name"] == "Dict Test"
            assert data["epic_id"] == "EPIC123"
            assert data["active"] is True
            assert data["status"] == "Active"
            assert data["class_year"] == "CA2"
            assert data["email"] == "test@example.com"
            assert data["phone"] == "555-1234"
            assert data["abbreviation"] == "DT"
            assert data["backup_id"] == "B123"
            assert data["total_entries"] == 0
            assert "time_entries" not in data

            db.session.delete(resident)
            db.session.commit()

    def test_to_dict_with_entries(self, app):
        """Test to_dict method with include_entries=True."""
        with app.app_context():
            resident = Resident(name="Dict Entries Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(name="Dict Entries Role", cutoff_hour=17, display_order=62)
            db.session.add(role)
            db.session.commit()

            entry = TimeEntry(
                date=date(2024, 6, 15),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
            )
            db.session.add(entry)
            db.session.commit()

            data = resident.to_dict(include_entries=True)

            assert "time_entries" in data
            assert len(data["time_entries"]) == 1
            assert data["time_entries"][0]["date"] == "2024-06-15"
            assert data["time_entries"][0]["role"] == "Dict Entries Role"

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_to_dict_without_created_at(self, app):
        """Test to_dict handles None created_at."""
        with app.app_context():
            # Create a resident object without persisting to test None created_at
            resident = Resident(name="No Created At", active=True)
            # Override the default before it gets set
            resident.created_at = None

            # Test to_dict on transient object
            data = resident.to_dict()
            assert data["created_at"] is None

    def test_to_dict_entry_without_role(self, app):
        """Test to_dict handles entry without role (transient object)."""
        with app.app_context():
            # Create transient objects to test None role scenario
            resident = Resident(name="Entry No Role Test", active=True)
            resident.created_at = datetime.now(UTC)

            # Create a mock entry with no role
            entry = TimeEntry(
                date=date(2024, 7, 1),
                exit_time=time(18, 0),
            )
            entry.role = None  # Explicitly set to None before adding to relationship

            # Add to resident's time_entries without persisting
            resident.time_entries.append(entry)

            data = resident.to_dict(include_entries=True)
            assert data["time_entries"][0]["role"] is None

    def test_get_active(self, app):
        """Test get_active classmethod."""
        with app.app_context():
            # Create active and inactive residents
            active1 = Resident(name="AAA Active One", active=True)
            active2 = Resident(name="BBB Active Two", active=True)
            inactive = Resident(name="CCC Inactive One", active=False)
            db.session.add_all([active1, active2, inactive])
            db.session.commit()

            actives = Resident.get_active()

            # Should include our active residents, sorted by name
            active_names = [r.name for r in actives]
            assert "AAA Active One" in active_names
            assert "BBB Active Two" in active_names
            assert "CCC Inactive One" not in active_names

            # Cleanup
            db.session.delete(active1)
            db.session.delete(active2)
            db.session.delete(inactive)
            db.session.commit()

    def test_get_by_epic_id_found(self, app):
        """Test get_by_epic_id when resident exists."""
        with app.app_context():
            resident = Resident(name="Epic Test", epic_id="EPIC_FIND_123", active=True)
            db.session.add(resident)
            db.session.commit()

            found = Resident.get_by_epic_id("EPIC_FIND_123")
            assert found is not None
            assert found.name == "Epic Test"

            db.session.delete(resident)
            db.session.commit()

    def test_get_by_epic_id_not_found(self, app):
        """Test get_by_epic_id when resident doesn't exist."""
        with app.app_context():
            found = Resident.get_by_epic_id("NONEXISTENT_EPIC_ID")
            assert found is None

    def test_get_or_create_by_epic_id_existing(self, app):
        """Test get_or_create finds existing resident by epic_id."""
        with app.app_context():
            existing = Resident(
                name="Existing Epic", epic_id="GOC_EPIC_001", active=True
            )
            db.session.add(existing)
            db.session.commit()

            resident, created = Resident.get_or_create(
                name="Different Name", epic_id="GOC_EPIC_001"
            )

            assert created is False
            assert resident.id == existing.id
            assert resident.name == "Existing Epic"

            db.session.delete(existing)
            db.session.commit()

    def test_get_or_create_by_name_existing(self, app):
        """Test get_or_create finds existing resident by name."""
        with app.app_context():
            existing = Resident(name="Name Match", active=True)
            db.session.add(existing)
            db.session.commit()

            resident, created = Resident.get_or_create(name="Name Match")

            assert created is False
            assert resident.id == existing.id

            db.session.delete(existing)
            db.session.commit()

    def test_get_or_create_by_name_adds_epic_id(self, app):
        """Test get_or_create adds epic_id to existing name-matched resident."""
        with app.app_context():
            existing = Resident(name="Name No Epic", epic_id=None, active=True)
            db.session.add(existing)
            db.session.commit()

            resident, created = Resident.get_or_create(
                name="Name No Epic", epic_id="NEW_EPIC_ID"
            )

            assert created is False
            assert resident.epic_id == "NEW_EPIC_ID"

            db.session.delete(existing)
            db.session.commit()

    def test_get_or_create_new(self, app):
        """Test get_or_create creates new resident."""
        with app.app_context():
            # Ensure no existing resident with this name/epic_id
            Resident.query.filter_by(name="Brand New Resident").delete()
            Resident.query.filter_by(epic_id="BRAND_NEW_EPIC").delete()
            db.session.commit()

            resident, created = Resident.get_or_create(
                name="Brand New Resident", epic_id="BRAND_NEW_EPIC"
            )
            db.session.commit()  # Commit the newly created resident

            assert created is True
            assert resident.name == "Brand New Resident"
            assert resident.epic_id == "BRAND_NEW_EPIC"

            db.session.delete(resident)
            db.session.commit()

    def test_get_entries_for_period(self, app):
        """Test get_entries_for_period method."""
        with app.app_context():
            resident = Resident(name="Period Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(name="Period Role", cutoff_hour=17, display_order=64)
            db.session.add(role)
            db.session.commit()

            # Create entries on different dates
            entry1 = TimeEntry(
                date=date(2024, 1, 10),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
            )
            entry2 = TimeEntry(
                date=date(2024, 1, 15),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
            )
            entry3 = TimeEntry(
                date=date(2024, 1, 20),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(18, 0),
            )
            db.session.add_all([entry1, entry2, entry3])
            db.session.commit()

            # Get entries in range
            entries = resident.get_entries_for_period(
                date(2024, 1, 12), date(2024, 1, 18)
            )

            assert len(entries) == 1
            assert entries[0].date == date(2024, 1, 15)

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_get_total_overtime_all(self, app):
        """Test get_total_overtime without date filters."""
        with app.app_context():
            resident = Resident(name="Total OT Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(
                name="Total OT Role", cutoff_hour=17, cutoff_minute=30, display_order=65
            )
            db.session.add(role)
            db.session.commit()

            # Create entries with known overtime (exit at 20:00, cutoff 17:30 = 2.5 hrs)
            entry1 = TimeEntry(
                date=date(2024, 2, 1),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(20, 0),  # 2.5 hours OT
            )
            entry2 = TimeEntry(
                date=date(2024, 2, 2),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(19, 30),  # 2.0 hours OT
            )
            db.session.add_all([entry1, entry2])
            db.session.commit()

            total = resident.get_total_overtime()
            assert total == 4.5

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_get_total_overtime_with_date_filter(self, app):
        """Test get_total_overtime with date filters."""
        with app.app_context():
            resident = Resident(name="Filtered OT Test", active=True)
            db.session.add(resident)
            db.session.commit()

            role = Role(
                name="Filtered OT Role",
                cutoff_hour=17,
                cutoff_minute=30,
                display_order=66,
            )
            db.session.add(role)
            db.session.commit()

            # Create entries on different dates
            entry1 = TimeEntry(
                date=date(2024, 3, 1),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(20, 0),  # 2.5 hours OT
            )
            entry2 = TimeEntry(
                date=date(2024, 3, 15),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(20, 0),  # 2.5 hours OT
            )
            entry3 = TimeEntry(
                date=date(2024, 3, 30),
                resident_id=resident.id,
                role_id=role.id,
                exit_time=time(20, 0),  # 2.5 hours OT
            )
            db.session.add_all([entry1, entry2, entry3])
            db.session.commit()

            # Get OT only for middle entry
            total = resident.get_total_overtime(date(2024, 3, 10), date(2024, 3, 20))
            assert total == 2.5

            # Cleanup - delete resident first (cascade handles time_entries)
            db.session.delete(resident)
            db.session.delete(role)
            db.session.commit()

    def test_resident_repr(self, app):
        """Test Resident __repr__ method."""
        with app.app_context():
            resident = Resident(name="Repr Resident", active=True)
            assert repr(resident) == "<Resident Repr Resident>"


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

    def test_overtime_backup_role_no_start_time_defaults_to_8am(
        self, app, sample_resident
    ):
        """Test backup role on weekend without start_time defaults to 8 AM."""
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

            # Should calculate from default start (08:00) to 17:00 = 9 hours
            overtime = entry.calculate_overtime_hours()
            assert overtime == 9.0

            db.session.delete(entry)
            db.session.delete(backup_role)
            db.session.commit()

    def test_overtime_backup_overnight_shift(self, app, sample_resident):
        """Test backup role overnight shift on weekend."""
        with app.app_context():
            backup_role = Role(
                name="Overnight Backup Test",
                cutoff_hour=17,
                cutoff_minute=30,
                is_backup=True,
                display_order=56,
            )
            db.session.add(backup_role)
            db.session.commit()

            # Create entry on a Saturday with overnight shift
            saturday = date(2024, 1, 6)
            entry = TimeEntry(
                date=saturday,
                resident_id=sample_resident.id,
                role_id=backup_role.id,
                start_time=time(20, 0),  # Started at 8 PM
                exit_time=time(6, 0),  # Left at 6 AM (next day)
            )
            db.session.add(entry)
            db.session.commit()

            # Should calculate overnight: 20:00 to 30:00 (6 AM next day) = 10 hours
            overtime = entry.calculate_overtime_hours()
            assert overtime == 10.0

            db.session.delete(entry)
            db.session.delete(backup_role)
            db.session.commit()

    def test_overtime_without_exit_time(self, app, sample_resident, sample_role):
        """Test overtime calculation without exit time returns 0."""
        with app.app_context():
            entry = TimeEntry(
                date=philly_today(),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.calculate_overtime_hours() == 0.0

            db.session.delete(entry)
            db.session.commit()

    def test_overtime_without_role(self, app, sample_resident, sample_role):
        """Test overtime calculation without role returns 0."""
        with app.app_context():
            # Create a transient entry without role to test the None role branch
            entry = TimeEntry(
                date=philly_today(),
                exit_time=time(20, 0),
            )
            entry.role = None

            assert entry.overtime_hours == 0.0

    def test_overtime_hours_property(self, app, sample_time_entry):
        """Test overtime_hours property."""
        with app.app_context():
            entry = db.session.get(TimeEntry, sample_time_entry.id)
            # Property should return same as method
            assert entry.overtime_hours == entry.calculate_overtime_hours()

    def test_time_entry_repr_with_resident(self, app, sample_resident, sample_role):
        """Test TimeEntry __repr__ with resident."""
        with app.app_context():
            entry = TimeEntry(
                date=date(2024, 5, 15),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=time(18, 0),
            )
            db.session.add(entry)
            db.session.commit()

            expected = f"<TimeEntry 2024-05-15 - {sample_resident.name}>"
            assert repr(entry) == expected

            db.session.delete(entry)
            db.session.commit()

    def test_time_entry_repr_without_resident(self, app, sample_role):
        """Test TimeEntry __repr__ without resident."""
        with app.app_context():
            # Create a transient entry without resident to test Unknown case
            entry = TimeEntry(
                date=date(2024, 5, 16),
                exit_time=time(18, 0),
            )
            entry.resident = None

            assert repr(entry) == "<TimeEntry 2024-05-16 - Unknown>"


class TestDailySheetModel:
    """Extended tests for DailySheet model."""

    def test_daily_sheet_repr(self, app):
        """Test DailySheet __repr__ method."""
        with app.app_context():
            sheet = DailySheet(date=date(2024, 8, 1), locked=False)
            assert repr(sheet) == "<DailySheet 2024-08-01>"


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

            with pytest.raises(IntegrityError):
                db.session.commit()

            db.session.rollback()

            # Cleanup
            db.session.delete(holiday1)
            db.session.commit()

    def test_holiday_is_holiday_true(self, app):
        """Test Holiday.is_holiday classmethod returns True for holiday."""
        with app.app_context():
            holiday = Holiday(
                date=date(2024, 7, 4),
                name="Independence Day",
                is_federal=True,
            )
            db.session.add(holiday)
            db.session.commit()

            assert Holiday.is_holiday(date(2024, 7, 4)) is True

            db.session.delete(holiday)
            db.session.commit()

    def test_holiday_is_holiday_false(self, app):
        """Test Holiday.is_holiday classmethod returns False for non-holiday."""
        with app.app_context():
            # Check a date that shouldn't be a holiday
            assert Holiday.is_holiday(date(2099, 6, 15)) is False

    def test_holiday_repr(self, app):
        """Test Holiday __repr__ method."""
        with app.app_context():
            holiday = Holiday(
                date=date(2024, 12, 25),
                name="Christmas",
                is_federal=True,
            )
            assert repr(holiday) == "<Holiday 2024-12-25 - Christmas>"


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_create_audit_log(self, app):
        """Test creating an audit log entry."""
        with app.app_context():
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

    def test_audit_log_repr(self, app):
        """Test AuditLog __repr__ method."""
        with app.app_context():
            timestamp = datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)
            log = AuditLog(
                timestamp=timestamp,
                user="Admin",
                action="CREATE",
                entity_type="TimeEntry",
                entity_id=42,
            )
            expected = "<AuditLog 2024-06-15 10:30:00+00:00 - Admin CREATE TimeEntry>"
            assert repr(log) == expected
