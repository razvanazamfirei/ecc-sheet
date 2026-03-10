"""Security-focused tests for schedule import routes."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from backend.models import DailySheet, Resident, Role, TimeEntry, db


@pytest.mark.integration
class TestScheduleImportSecurity:
    """Tests covering schedule import security behavior."""

    @patch("backend.routes.schedule.requests.get")
    def test_import_allows_regular_user_before_first_call_known(
        self, mock_get, client, app, monkeypatch
    ):
        """Regular users can import schedules before first-call is known."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        with app.app_context():
            test_date = date(2024, 4, 7)
            role = Role.query.filter_by(name="ECC 1").first()
            assert role is not None
            role_id = role.id

            resident = Resident(
                name="Open Import Resident",
                epic_id="R23456",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()
            resident_id = resident.id

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"Open Import Resident","EPICID:R23456","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

        try:
            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert (
                b"Successfully imported 1 schedule entries from Amion" in response.data
            )

            with app.app_context():
                entry = TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident_id,
                    role_id=role_id,
                ).first()
                assert entry is not None
        finally:
            with app.app_context():
                entry = TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=resident_id,
                    role_id=role_id,
                ).first()
                if entry is not None:
                    db.session.delete(entry)
                resident = db.session.get(Resident, resident_id)
                if resident is not None:
                    db.session.delete(resident)
                db.session.commit()

    @patch("backend.routes.schedule.requests.get")
    def test_import_uses_https_amion_base_url(self, mock_get, client, app):
        """Schedule imports default to HTTPS when AMION_BASE_URL is unset."""
        with app.app_context():
            test_date = date(2024, 4, 2)

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet:
                sheet.locked = False
                db.session.commit()

            role = Role.query.filter_by(name="ECC 1").first()
            if role is None:
                role = Role(name="ECC 1", cutoff_hour=17, display_order=1)
                db.session.add(role)
                db.session.commit()

            resident = Resident(
                name="HTTPS Schedule Resident",
                epic_id="R12345",
                active=True,
            )
            db.session.add(resident)
            db.session.commit()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = (
                '"HTTPS Schedule Resident","EPICID:R12345","","ECC 1","","","","",""\n'
            )
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response

            response = client.post(
                f"/schedule/{test_date.strftime('%Y-%m-%d')}/import",
                follow_redirects=True,
            )

            assert response.status_code == 200
            assert mock_get.call_args is not None
            assert mock_get.call_args.args[0].startswith("https://")

            TimeEntry.query.filter_by(
                date=test_date, resident_id=resident.id, role_id=role.id
            ).delete()
            db.session.delete(resident)
            db.session.commit()
