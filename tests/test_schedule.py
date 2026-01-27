"""Tests for schedule import functionality."""

from datetime import date
from unittest.mock import MagicMock, patch

from backend.models import DailySheet, Role, db


class TestScheduleImport:
    """Tests for schedule import routes."""

    def test_import_locked_sheet(self, client, app):
        """Test import fails on locked sheet."""
        with app.app_context():
            # Create and lock a sheet
            test_date = date(2024, 3, 15)
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if not sheet:
                sheet = DailySheet(date=test_date, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            db.session.commit()

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"locked" in response.data.lower()

            # Cleanup
            sheet.locked = False
            db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_success(self, mock_get, client, app):
        """Test successful schedule import."""
        with app.app_context():
            test_date = date(2024, 3, 16)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Make sure we have a role to import to
            role = Role.query.filter_by(name="ECC 1").first()
            if not role:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            # Mock the Amion response with valid CSV data
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                "Field1,Field2,Field3,Field4,Field5,Field6,Field7,EPICID,Field9\n"
                "ECC 1,Test Resident,Some,Data,Here,More,Data,EPICID:R12345,Extra"
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_request_error(self, mock_get, client, app):
        """Test schedule import with network error."""
        import requests

        with app.app_context():
            test_date = date(2024, 3, 17)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock network error
            mock_get.side_effect = requests.RequestException("Network error")

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should show error message

    @patch("backend.routes.schedule.requests.get")
    def test_import_schedule_empty_response(self, mock_get, client, app):
        """Test schedule import with empty CSV."""
        with app.app_context():
            test_date = date(2024, 3, 18)

            # Ensure sheet is unlocked
            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            # Mock empty response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = ""
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200

    def test_import_invalid_date(self, client):
        """Test import with invalid date format."""
        response = client.post(
            "/schedule/invalid-date/import",
            follow_redirects=True,
        )
        # Should handle the error
        assert response.status_code in {200, 400, 404}
