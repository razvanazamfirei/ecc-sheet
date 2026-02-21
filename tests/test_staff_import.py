"""Tests for staff import functionality."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.models import Resident, db
from backend.staff_import import (
    fetch_staff_list,
    import_staff_list,
    import_staff_to_database,
    parse_staff_list,
)
from backend.type_defs import StaffRecord


class TestFetchStaffList:
    """Tests for fetch_staff_list function."""

    @patch("backend.staff_import.requests.get")
    def test_fetch_success(self, mock_get):
        """Test successful staff list fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Staff type\tName\nResident\tJohn Doe"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = fetch_staff_list("testcode")

        assert "Staff type" in result
        mock_get.assert_called_once_with(
            "http://www.amion.com/cgi-bin/ocs?Lo=testcode&Rpt=706", timeout=30
        )

    @patch("backend.staff_import.requests.get")
    def test_fetch_with_custom_schedule_code(self, mock_get):
        """Test fetch with custom schedule code."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "data"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        fetch_staff_list(schedule_code="custom")

        call_url = mock_get.call_args[0][0]
        assert "Lo=custom" in call_url
        assert "Rpt=706" in call_url

    @patch("backend.staff_import.requests.get")
    def test_fetch_network_error(self, mock_get):
        """Test network error handling."""
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(requests.RequestException, match="Network error"):
            fetch_staff_list("testcode")

    @patch("backend.staff_import.requests.get")
    def test_fetch_http_error(self, mock_get):
        """Test HTTP error handling via raise_for_status."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        with pytest.raises(requests.HTTPError, match="404 Not Found"):
            fetch_staff_list("testcode")


class TestParseStaffList:
    """Tests for parse_staff_list function."""

    def test_parse_valid_csv_with_epic_ids(self):
        """Test parsing valid CSV content with EPIC IDs."""
        csv_content = """Some header info
Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tJohn Doe\tEPICID:R12345\tB001\tJD\t1\t555-1234\t555-5678\tjohn@example.com
CA2\tJane Smith\tEPICID:R67890\t\tJS\t2\t\t555-9999\tjane@example.com
"""
        result = parse_staff_list(csv_content)

        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[0]["epic_id"] == "R12345"
        assert result[0]["class_year"] == "CA1"
        assert result[0]["backup_id"] == "B001"
        assert result[0]["abbreviation"] == "JD"
        assert result[0]["phone"] == "555-1234"
        assert result[0]["email"] == "john@example.com"

        assert result[1]["name"] == "Jane Smith"
        assert result[1]["epic_id"] == "R67890"
        assert result[1]["phone"] == "555-9999"  # Falls back to Tel.

    def test_parse_empty_content(self):
        """Test parsing empty content raises error."""
        with pytest.raises(ValueError, match="Could not find header"):
            parse_staff_list("")

    def test_parse_no_header(self):
        """Test parsing content without header raises error."""
        csv_content = "Some random content\nNo header here"
        with pytest.raises(ValueError, match="Could not find header"):
            parse_staff_list(csv_content)

    def test_parse_only_header(self):
        """Test parsing content with only header."""
        csv_content = "Staff type\tName\tUnique ID"
        result = parse_staff_list(csv_content)
        assert result == []

    def test_parse_skips_empty_names(self):
        """Test that rows with empty names are skipped."""
        csv_content = """Staff type\tName\tUnique ID
CA1\t\tEPICID:R12345
CA2\tJane Smith\tEPICID:R67890
"""
        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "Jane Smith"

    def test_parse_skips_placeholder_entries(self):
        """Test that placeholder entries are skipped."""
        csv_content = """Staff type\tName\tUnique ID
CA1\tPlaceholder Resident\tEPICID:R00001
CA2\tTest PLACEHOLDER\tEPICID:R00002
CA3\tJohn Doe\tEPICID:R12345
"""
        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "John Doe"

    def test_parse_skips_entries_without_epic_id(self):
        """Test that entries without valid EPIC IDs are skipped."""
        csv_content = """Staff type\tName\tUnique ID
CA1\tNo Epic Person\tSOMEOTHER:12345
CA2\tEmpty Epic\t
CA3\tJohn Doe\tEPICID:R12345
"""
        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "John Doe"

    def test_parse_uses_pager_before_tel(self):
        """Test that Pager field is preferred over Tel. for phone."""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tJohn Doe\tEPICID:R12345\t\tJD\t1\t555-PAGER\t555-TEL\tjohn@example.com
"""  # noqa: E501
        result = parse_staff_list(csv_content)

        assert result[0]["phone"] == "555-PAGER"

    def test_parse_falls_back_to_tel_when_no_pager(self):
        """Test that Tel. is used when Pager is empty."""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tJohn Doe\tEPICID:R12345\t\tJD\t1\t\t555-TEL\tjohn@example.com
"""  # noqa: E501
        result = parse_staff_list(csv_content)

        assert result[0]["phone"] == "555-TEL"

    def test_parse_handles_whitespace_in_names(self):
        """Test that whitespace is stripped from names."""
        csv_content = """Staff type\tName\tUnique ID
CA1\t  John Doe  \tEPICID:R12345
"""
        result = parse_staff_list(csv_content)

        assert result[0]["name"] == "John Doe"

    def test_parse_handles_whitespace_only_names(self):
        """Test that names with only whitespace are skipped."""
        csv_content = """Staff type\tName\tUnique ID
CA1\t   \tEPICID:R12345
CA2\tJane Smith\tEPICID:R67890
"""
        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "Jane Smith"


class TestImportStaffToDatabase:
    """Tests for import_staff_to_database function."""

    def test_create_new_resident(self, app):
        """Test creating a new resident from staff list."""
        with app.app_context():
            # Clean up any existing test residents
            Resident.query.filter(Resident.epic_id.like("TEST_%")).delete()
            db.session.commit()

            staff_list: list[StaffRecord] = [
                {
                    "name": "New Test Resident",
                    "epic_id": "TEST_NEW_001",
                    "class_year": "CA1",
                    "email": "new@test.com",
                    "phone": "555-1234",
                    "abbreviation": "NTR",
                    "backup_id": "B001",
                }
            ]

            created, updated, skipped = import_staff_to_database(
                staff_list, user="test_user"
            )

            assert created == 1
            assert updated == 0
            assert skipped == 0

            # Verify resident was created
            resident = Resident.get_by_epic_id("TEST_NEW_001")
            assert resident is not None
            assert resident.name == "New Test Resident"
            assert resident.class_year == "CA-1"
            assert resident.email == "new@test.com"
            assert resident.phone == "555-1234"
            assert resident.abbreviation == "NTR"
            assert resident.backup_id == "B001"
            assert resident.active is True

            # Cleanup
            db.session.delete(resident)
            db.session.commit()

    def test_update_existing_resident(self, app):
        """Test updating an existing resident with changed information."""
        with app.app_context():
            # Create an existing resident with canonical class_year
            existing = Resident(
                name="Old Name",
                first_name="Old",
                last_name="Name",
                epic_id="TEST_UPDATE_001",
                class_year="CA-1",
                email="old@test.com",
                phone="555-0000",
                abbreviation="OLD",
                backup_id="OLD_B",
                active=True,
            )
            db.session.add(existing)
            db.session.commit()

            staff_list: list[StaffRecord] = [
                {
                    "name": "Updated Name",
                    "epic_id": "TEST_UPDATE_001",
                    "class_year": "CA2",
                    "email": "updated@test.com",
                    "phone": "555-9999",
                    "abbreviation": "UPD",
                    "backup_id": "NEW_B",
                }
            ]

            created, updated, skipped = import_staff_to_database(
                staff_list, user="test_user"
            )

            assert created == 0
            assert updated == 1
            assert skipped == 0

            # Verify resident was updated
            resident = Resident.get_by_epic_id("TEST_UPDATE_001")
            assert resident is not None
            assert resident.name == "Updated Name"
            assert resident.class_year == "CA-2"
            assert resident.email == "updated@test.com"
            assert resident.phone == "555-9999"
            assert resident.abbreviation == "UPD"
            assert resident.backup_id == "NEW_B"

            # Cleanup
            db.session.delete(resident)
            db.session.commit()

    def test_skip_unchanged_resident(self, app):
        """Test that unchanged residents are skipped."""
        with app.app_context():
            # Create an existing resident with already-normalized class_year and
            # pre-split names
            existing = Resident(
                name="Same Name",
                first_name="Same",
                last_name="Name",
                epic_id="TEST_SKIP_001",
                class_year="CA-1",
                email="same@test.com",
                phone="555-1111",
                abbreviation="SAM",
                backup_id="B001",
                active=True,
            )
            db.session.add(existing)
            db.session.commit()

            # Import with same data using Amion-style class_year (maps to "CA-1")
            staff_list: list[StaffRecord] = [
                {
                    "name": "Same Name",
                    "epic_id": "TEST_SKIP_001",
                    "class_year": "CA1",
                    "email": "same@test.com",
                    "phone": "555-1111",
                    "abbreviation": "SAM",
                    "backup_id": "B001",
                }
            ]

            created, updated, skipped = import_staff_to_database(
                staff_list, user="test_user"
            )

            assert created == 0
            assert updated == 0
            assert skipped == 1

            # Cleanup
            db.session.delete(existing)
            db.session.commit()

    def test_mixed_operations(self, app):
        """Test a mix of create, update, and skip operations."""
        with app.app_context():
            # Clean up any existing test residents
            Resident.query.filter(Resident.epic_id.like("TEST_MIX_%")).delete()
            db.session.commit()

            # Create existing residents with canonical class_year values
            # and pre-split names
            existing_unchanged = Resident(
                name="Unchanged",
                first_name="Unchanged",
                last_name=None,
                epic_id="TEST_MIX_001",
                class_year="CA-1",
                email="unchanged@test.com",
                phone="555-0001",
                abbreviation="UNC",
                backup_id="",
                active=True,
            )
            existing_to_update = Resident(
                name="To Update",
                first_name="To",
                last_name="Update",
                epic_id="TEST_MIX_002",
                class_year="CA-1",
                email="old@test.com",
                phone="555-0002",
                abbreviation="TOU",
                backup_id="",
                active=True,
            )
            db.session.add_all([existing_unchanged, existing_to_update])
            db.session.commit()

            staff_list: list[StaffRecord] = [
                {
                    "name": "Unchanged",
                    "epic_id": "TEST_MIX_001",
                    "class_year": "CA1",  # Maps to "CA-1" (unchanged)
                    "email": "unchanged@test.com",
                    "phone": "555-0001",
                    "abbreviation": "UNC",
                    "backup_id": "",
                },
                {
                    "name": "To Update",
                    "epic_id": "TEST_MIX_002",
                    "class_year": "CA2",  # Maps to "CA-2" (changed)
                    "email": "old@test.com",
                    "phone": "555-0002",
                    "abbreviation": "TOU",
                    "backup_id": "",
                },
                {
                    "name": "New Resident",
                    "epic_id": "TEST_MIX_003",
                    "class_year": "CA3",
                    "email": "new@test.com",
                    "phone": "555-0003",
                    "abbreviation": "NEW",
                    "backup_id": "",
                },
            ]

            created, updated, skipped = import_staff_to_database(
                staff_list, user="test_user"
            )

            assert created == 1
            assert updated == 1
            assert skipped == 1

            # Cleanup
            Resident.query.filter(Resident.epic_id.like("TEST_MIX_%")).delete()
            db.session.commit()

    def test_partial_field_updates(self, app):
        """Test that only changed fields trigger an update."""
        with app.app_context():
            # Create an existing resident with canonical class_year and pre-split names
            existing = Resident(
                name="Test Person",
                first_name="Test",
                last_name="Person",
                epic_id="TEST_PARTIAL_001",
                class_year="CA-1",
                email="test@test.com",
                phone="555-1111",
                abbreviation="TST",
                backup_id="B001",
                active=True,
            )
            db.session.add(existing)
            db.session.commit()

            # Change only the email; class_year "CA1" maps to "CA-1" (no change)
            staff_list: list[StaffRecord] = [
                {
                    "name": "Test Person",
                    "epic_id": "TEST_PARTIAL_001",
                    "class_year": "CA1",
                    "email": "newemail@test.com",  # Only this changed
                    "phone": "555-1111",
                    "abbreviation": "TST",
                    "backup_id": "B001",
                }
            ]

            created, updated, skipped = import_staff_to_database(
                staff_list, user="test_user"
            )

            assert created == 0
            assert updated == 1
            assert skipped == 0

            # Verify only email changed; class_year remains "CA-1"
            resident = Resident.get_by_epic_id("TEST_PARTIAL_001")
            assert resident is not None
            assert resident.email == "newemail@test.com"
            assert resident.class_year == "CA-1"  # Unchanged (CA1 → CA-1)

            # Cleanup
            db.session.delete(resident)
            db.session.commit()


class TestImportStaffList:
    """Tests for import_staff_list complete workflow function."""

    @patch("backend.staff_import.fetch_staff_list")
    def test_success_flow(self, mock_fetch, app):
        """Test successful complete import workflow."""
        with app.app_context():
            # Clean up
            Resident.query.filter(Resident.epic_id.like("TEST_FLOW_%")).delete()
            db.session.commit()

            mock_fetch.return_value = """Header line
Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tFlow Test\tEPICID:TEST_FLOW_001\t\tFT\t1\t\t\tflow@test.com
"""
            result = import_staff_list(schedule_code="testcode", user="test_user")

            assert result["success"] is True
            assert result["created"] == 1
            assert result["updated"] == 0
            assert result["skipped"] == 0
            assert result["total_records"] == 1
            assert result["error"] is None

            # Cleanup
            Resident.query.filter(Resident.epic_id.like("TEST_FLOW_%")).delete()
            db.session.commit()

    @patch("backend.staff_import.fetch_staff_list")
    def test_empty_staff_list(self, mock_fetch, app):
        """Test import with no valid staff records."""
        with app.app_context():
            # Return CSV with only placeholders/invalid entries
            mock_fetch.return_value = """Header line
Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tPlaceholder\tEPICID:R00001\t\tPH\t1\t\t\tph@test.com
CA2\t\tEPICID:R00002\t\tEM\t2\t\t\t
"""
            result = import_staff_list(schedule_code="testcode", user="test_user")

            assert result["success"] is False
            assert result["error"] == "No staff records found in import"
            assert result["created"] == 0
            assert result["updated"] == 0
            assert result["skipped"] == 0
            assert result["total_records"] == 0

    @patch("backend.staff_import.fetch_staff_list")
    def test_network_error(self, mock_fetch, app):
        """Test import with network error."""
        with app.app_context():
            mock_fetch.side_effect = requests.RequestException("Connection failed")

            result = import_staff_list(schedule_code="testcode", user="test_user")

            assert result["success"] is False
            error = result["error"]
            assert error is not None
            assert "Failed to fetch staff list from Amion" in error
            assert "Connection failed" in error
            assert result["created"] == 0
            assert result["total_records"] == 0

    @patch("backend.staff_import.fetch_staff_list")
    def test_parse_error(self, mock_fetch, app):
        """Test import with parse error (no header)."""
        with app.app_context():
            mock_fetch.return_value = "Invalid content without header"

            result = import_staff_list(schedule_code="testcode", user="test_user")

            assert result["success"] is False
            error = result["error"]
            assert error is not None
            assert "Import failed" in error
            assert "Could not find header" in error
            assert result["created"] == 0
            assert result["total_records"] == 0

    @patch("backend.staff_import.fetch_staff_list")
    def test_custom_schedule_code(self, mock_fetch, app):
        """Test import with custom schedule code."""
        with app.app_context():
            mock_fetch.return_value = """Staff type\tName\tUnique ID
CA1\tCustom Test\tEPICID:TEST_CUSTOM_001
"""
            # Clean up
            Resident.query.filter(Resident.epic_id.like("TEST_CUSTOM_%")).delete()
            db.session.commit()

            result = import_staff_list(schedule_code="custom_code", user="test_user")

            mock_fetch.assert_called_once_with("custom_code")
            assert result["success"] is True

            # Cleanup
            Resident.query.filter(Resident.epic_id.like("TEST_CUSTOM_%")).delete()
            db.session.commit()

    @patch("backend.staff_import.fetch_staff_list")
    @patch("backend.staff_import.import_staff_to_database")
    def test_database_error(self, mock_import_db, mock_fetch, app):
        """Test import with database error."""
        with app.app_context():
            mock_fetch.return_value = """Staff type\tName\tUnique ID
CA1\tTest Person\tEPICID:R12345
"""
            mock_import_db.side_effect = Exception("Database connection lost")

            result = import_staff_list(schedule_code="testcode", user="test_user")

            assert result["success"] is False
            error = result["error"]
            assert error is not None
            assert "Import failed" in error
            assert "Database connection lost" in error


class TestImportStaffRoute:
    """Tests for staff import route."""

    @patch("backend.staff_import.fetch_staff_list")
    def test_import_staff_success(self, mock_fetch, client, app):
        """Test successful staff import via route."""
        with app.app_context():
            # Clean up
            Resident.query.filter(Resident.epic_id.like("ROUTE_TEST_%")).delete()
            db.session.commit()

            mock_fetch.return_value = """Header line
Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tType ID\tPager\tTel.\tEmail
CA1\tRoute Test Person\tEPICID:ROUTE_TEST_001\t\tRTP\t1\t\t\troute@test.com
"""
            response = client.post("/residents/import", follow_redirects=True)
            assert response.status_code == 200

            # Cleanup
            Resident.query.filter(Resident.epic_id.like("ROUTE_TEST_%")).delete()
            db.session.commit()

    @patch("backend.staff_import.fetch_staff_list")
    def test_import_staff_network_error(self, mock_fetch, client, app):
        """Test staff import with network error via route."""
        with app.app_context():
            mock_fetch.side_effect = requests.RequestException("Network error")

            response = client.post("/residents/import", follow_redirects=True)
            assert response.status_code == 200
            # Should show error message in flashed messages
