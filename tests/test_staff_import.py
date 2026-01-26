"""
Tests for staff import functionality
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.staff_import import (
    get_class_year_display_name,
    import_staff_to_database,
    parse_staff_list,
)


class TestParseStaffList:
    """Test staff list CSV parsing"""

    def test_parse_valid_csv(self):
        """Test parsing a valid staff list CSV"""
        csv_content = """Some header info
More header info
Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tStaff type unique ID\tPager\tTel.\tEmail
CA1\tJohn Doe\tEPICID:R123456\tBID001\tJD\tCA1-001\t555-1234\t555-5678\tjohn.doe@example.com
CA2\tJane Smith\tEPICID:R789012\tBID002\tJS\tCA2-001\t\t555-8765\tjane.smith@example.com"""  # noqa: E501

        result = parse_staff_list(csv_content)

        assert len(result) == 2
        assert result[0]["name"] == "John Doe"
        assert result[0]["epic_id"] == "R123456"
        assert result[0]["class_year"] == "CA1"
        assert result[0]["email"] == "john.doe@example.com"
        assert result[0]["phone"] == "555-1234"
        assert result[0]["abbreviation"] == "JD"
        assert result[0]["backup_id"] == "BID001"

        assert result[1]["name"] == "Jane Smith"
        assert result[1]["epic_id"] == "R789012"
        assert result[1]["class_year"] == "CA2"
        # Phone should fall back to Tel. when Pager is empty
        assert result[1]["phone"] == "555-8765"

    def test_parse_skips_empty_names(self):
        """Test that empty names are skipped"""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tStaff type unique ID\tPager\tTel.\tEmail
CA1\t\tEPICID:R123456\tBID001\tJD\tCA1-001\t555-1234\t\tjohn@example.com
CA1\tJohn Doe\tEPICID:R123457\tBID002\tJD2\tCA1-002\t555-1235\t\tjohn2@example.com"""  # noqa: E501

        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "John Doe"

    def test_parse_skips_placeholders(self):
        """Test that placeholder entries are skipped"""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tStaff type unique ID\tPager\tTel.\tEmail
CA1\tPlaceholder Resident\tEPICID:R123456\tBID001\tPH\tCA1-001\t555-1234\t\tplaceholder@example.com
CA1\tJohn Doe\tEPICID:R123457\tBID002\tJD\tCA1-002\t555-1235\t\tjohn@example.com"""  # noqa: E501

        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "John Doe"

    def test_parse_skips_entries_without_epic_id(self):
        """Test that entries without EPIC ID are skipped"""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tStaff type unique ID\tPager\tTel.\tEmail
CA1\tJohn Doe\t\tBID001\tJD\tCA1-001\t555-1234\t\tjohn@example.com
CA1\tJane Smith\tEPICID:R789012\tBID002\tJS\tCA2-001\t555-4321\t\tjane@example.com
CA1\tBob Wilson\tOTHERID:12345\tBID003\tBW\tCA1-003\t555-9999\t\tbob@example.com"""  # noqa: E501

        result = parse_staff_list(csv_content)

        assert len(result) == 1
        assert result[0]["name"] == "Jane Smith"

    def test_parse_raises_on_missing_header(self):
        """Test that parsing raises error when header is missing"""
        csv_content = """Some random content
Without proper header
Just random lines"""

        with pytest.raises(ValueError, match="Could not find header line"):
            parse_staff_list(csv_content)

    def test_parse_handles_whitespace_in_names(self):
        """Test that whitespace in names is stripped"""
        csv_content = """Staff type\tName\tUnique ID\tBackup ID\tAbbreviation\tStaff type unique ID\tPager\tTel.\tEmail
CA1\t  John Doe  \tEPICID:R123456\tBID001\tJD\tCA1-001\t555-1234\t\tjohn@example.com"""  # noqa: E501

        result = parse_staff_list(csv_content)

        assert result[0]["name"] == "John Doe"


class TestGetClassYearDisplayName:
    """Test class year display name mapping"""

    def test_ca1_display_name(self):
        """Test CA1 display name"""
        assert get_class_year_display_name("CA1") == "CA-1 (First Year)"

    def test_ca2_display_name(self):
        """Test CA2 display name"""
        assert get_class_year_display_name("CA2") == "CA-2 (Second Year)"

    def test_ca3_display_name(self):
        """Test CA3 display name"""
        assert get_class_year_display_name("CA3") == "CA-3 (Third Year)"

    def test_fellow_display_name(self):
        """Test Fellow display name"""
        assert get_class_year_display_name("Fellow") == "Fellow"

    def test_omfs_display_name(self):
        """Test OMFS display name"""
        assert get_class_year_display_name("OMFS") == "Oral & Maxillofacial Surgery"

    def test_unknown_class_year_returns_original(self):
        """Test that unknown class years return the original value"""
        assert get_class_year_display_name("Unknown") == "Unknown"
        assert get_class_year_display_name("CA4") == "CA4"
        assert not get_class_year_display_name("")


class TestImportStaffToDatabase:
    """Test staff import to database"""

    @pytest.fixture
    def mock_resident_class(self):
        """Create a mock Resident class"""
        with patch("backend.staff_import.Resident") as mock:
            yield mock

    @pytest.fixture
    def mock_db(self):
        """Create a mock db session"""
        with patch("backend.staff_import.db") as mock:
            yield mock

    @pytest.fixture
    def mock_log_import(self):
        """Create a mock log_import function"""
        with patch("backend.staff_import.log_import") as mock:
            yield mock

    def test_creates_new_residents(
        self, app, mock_resident_class, mock_db, mock_log_import
    ):
        """Test that new residents are created"""
        mock_resident_class.get_by_epic_id.return_value = None

        staff_list = [
            {
                "name": "John Doe",
                "epic_id": "R123456",
                "class_year": "CA1",
                "email": "john@example.com",
                "phone": "555-1234",
                "abbreviation": "JD",
                "backup_id": "BID001",
            }
        ]

        with app.app_context():
            created, updated, skipped = import_staff_to_database(
                staff_list, user="TestUser"
            )

        assert created == 1
        assert updated == 0
        assert skipped == 0
        mock_resident_class.assert_called_once()
        mock_db.session.add.assert_called_once()
        mock_db.session.commit.assert_called_once()
        mock_log_import.assert_called_once()

    def test_updates_existing_residents(
        self, app, mock_resident_class, mock_db, mock_log_import
    ):
        """Test that existing residents are updated when data changes"""
        existing_resident = MagicMock()
        existing_resident.class_year = "CA1"
        existing_resident.email = "old@example.com"
        existing_resident.phone = "555-0000"
        existing_resident.abbreviation = "JD"
        existing_resident.backup_id = "BID001"
        existing_resident.name = "John Doe"
        mock_resident_class.get_by_epic_id.return_value = existing_resident

        staff_list = [
            {
                "name": "John Doe",
                "epic_id": "R123456",
                "class_year": "CA2",  # Changed
                "email": "new@example.com",  # Changed
                "phone": "555-0000",
                "abbreviation": "JD",
                "backup_id": "BID001",
            }
        ]

        with app.app_context():
            created, updated, skipped = import_staff_to_database(
                staff_list, user="TestUser"
            )

        assert created == 0
        assert updated == 1
        assert skipped == 0
        assert existing_resident.class_year == "CA2"
        assert existing_resident.email == "new@example.com"

    def test_skips_unchanged_residents(
        self, app, mock_resident_class, mock_db, mock_log_import
    ):
        """Test that unchanged residents are skipped"""
        existing_resident = MagicMock()
        existing_resident.class_year = "CA1"
        existing_resident.email = "john@example.com"
        existing_resident.phone = "555-1234"
        existing_resident.abbreviation = "JD"
        existing_resident.backup_id = "BID001"
        existing_resident.name = "John Doe"
        mock_resident_class.get_by_epic_id.return_value = existing_resident

        staff_list = [
            {
                "name": "John Doe",
                "epic_id": "R123456",
                "class_year": "CA1",
                "email": "john@example.com",
                "phone": "555-1234",
                "abbreviation": "JD",
                "backup_id": "BID001",
            }
        ]

        with app.app_context():
            created, updated, skipped = import_staff_to_database(
                staff_list, user="TestUser"
            )

        assert created == 0
        assert updated == 0
        assert skipped == 1

    def test_logs_import_action(
        self, app, mock_resident_class, mock_db, mock_log_import
    ):
        """Test that import action is logged"""
        mock_resident_class.get_by_epic_id.return_value = None

        staff_list = [
            {
                "name": "John Doe",
                "epic_id": "R123456",
                "class_year": "CA1",
                "email": "john@example.com",
                "phone": "555-1234",
                "abbreviation": "JD",
                "backup_id": "BID001",
            }
        ]

        with app.app_context():
            import_staff_to_database(staff_list, user="TestUser")

        mock_log_import.assert_called_once_with(
            "staff_list", "Created: 1, Updated: 0, Skipped: 0", user="TestUser"
        )
