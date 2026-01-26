"""Tests for report utilities."""

from datetime import date, time

import pytest

from backend.models import Resident, Role, TimeEntry, db
from backend.report_utils import (
    aggregate_entries_by_resident,
    build_entries_query,
    generate_csv_content,
    get_resident_name,
)


class TestBuildEntriesQuery:
    """Tests for build_entries_query function."""

    def test_query_with_date_range(self, app):
        """Test building query with date range."""
        with app.app_context():
            start = date(2024, 1, 1)
            end = date(2024, 1, 31)
            query = build_entries_query(start, end, None)
            # Query should be built without error
            assert query is not None

    def test_query_with_resident_filter(self, app, sample_resident):
        """Test building query with resident filter."""
        with app.app_context():
            start = date(2024, 1, 1)
            end = date(2024, 1, 31)
            query = build_entries_query(start, end, sample_resident.id)
            assert query is not None


class TestGetResidentName:
    """Tests for get_resident_name function."""

    def test_returns_none_for_none_id(self, app):
        """Test that None is returned for None resident_id."""
        with app.app_context():
            assert get_resident_name(None) is None

    def test_returns_none_for_empty_string(self, app):
        """Test that None is returned for empty string resident_id."""
        with app.app_context():
            assert get_resident_name("") is None

    def test_returns_name_for_valid_id(self, app, sample_resident):
        """Test that name is returned for valid resident_id."""
        with app.app_context():
            name = get_resident_name(sample_resident.id)
            assert name == sample_resident.name

    def test_returns_none_for_invalid_id(self, app):
        """Test that None is returned for non-existent resident_id."""
        with app.app_context():
            assert get_resident_name(99999) is None


class TestAggregateEntriesByResident:
    """Tests for aggregate_entries_by_resident function."""

    def test_empty_entries(self, app):
        """Test aggregation with empty entries list."""
        with app.app_context():
            result = aggregate_entries_by_resident([])
            assert result == {}

    def test_single_entry(self, app, sample_time_entry):
        """Test aggregation with single entry."""
        with app.app_context():
            # Reload entry in current session
            entry = TimeEntry.query.get(sample_time_entry.id)
            result = aggregate_entries_by_resident([entry])

            assert len(result) == 1
            assert entry.resident.name in result
            assert len(result[entry.resident.name]["entries"]) == 1
            assert result[entry.resident.name]["total_overtime"] >= 0

    def test_multiple_entries_same_resident(self, app, sample_resident, sample_role):
        """Test aggregation with multiple entries for same resident."""
        with app.app_context():
            # Create multiple entries
            entries = []
            for i in range(3):
                entry = TimeEntry(
                    date=date(2024, 1, i + 1),
                    resident_id=sample_resident.id,
                    role_id=sample_role.id,
                    exit_time=time(19, 0),
                )
                db.session.add(entry)
                entries.append(entry)
            db.session.commit()

            # Reload entries
            entries = TimeEntry.query.filter(
                TimeEntry.resident_id == sample_resident.id
            ).all()

            result = aggregate_entries_by_resident(entries)

            assert len(result) == 1
            assert sample_resident.name in result
            assert len(result[sample_resident.name]["entries"]) == len(entries)

            # Cleanup
            for entry in entries:
                db.session.delete(entry)
            db.session.commit()

    def test_entry_without_exit_time(self, app, sample_resident, sample_role):
        """Test aggregation with entry missing exit time."""
        with app.app_context():
            entry = TimeEntry(
                date=date(2024, 1, 1),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()

            entries = [TimeEntry.query.get(entry.id)]
            result = aggregate_entries_by_resident(entries)

            assert len(result) == 1
            # Exit time should be empty string
            assert result[sample_resident.name]["entries"][0]["exit_time"] == ""

            db.session.delete(entry)
            db.session.commit()


class TestGenerateCsvContent:
    """Tests for generate_csv_content function."""

    def test_empty_entries(self, app):
        """Test CSV generation with empty entries."""
        with app.app_context():
            csv_content = generate_csv_content([])
            lines = csv_content.strip().split("\n")
            assert len(lines) == 1  # Just header
            assert "Date" in lines[0]
            assert "Resident" in lines[0]

    def test_single_entry(self, app, sample_time_entry):
        """Test CSV generation with single entry."""
        with app.app_context():
            entry = TimeEntry.query.get(sample_time_entry.id)
            csv_content = generate_csv_content([entry])

            lines = csv_content.strip().split("\n")
            assert len(lines) == 2  # Header + 1 entry
            assert entry.resident.name in lines[1]
            assert entry.role.name in lines[1]

    def test_entry_without_exit_time(self, app, sample_resident, sample_role):
        """Test CSV generation with entry missing exit time."""
        with app.app_context():
            entry = TimeEntry(
                date=date(2024, 1, 1),
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()

            entries = [TimeEntry.query.get(entry.id)]
            csv_content = generate_csv_content(entries)

            # Should not raise error
            assert csv_content is not None
            lines = csv_content.strip().split("\n")
            assert len(lines) == 2

            db.session.delete(entry)
            db.session.commit()
