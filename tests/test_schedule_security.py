"""Security-focused tests for schedule import routes."""

import os
from datetime import date
from unittest.mock import MagicMock, patch

from backend.models import DailySheet, Resident, Role, TimeEntry, db


class TestScheduleImportSecurity:
    """Tests covering schedule import security behavior."""

    def test_import_requires_editor_role(self, client, app):
        """Regular non-editor users cannot trigger schedule imports."""
        original_admin_users = os.environ.get("ADMIN_USERS", "")
        original_user_name = os.environ.get("USER_NAME", "")

        try:
            os.environ["USER_NAME"] = "Regular User"
            os.environ["ADMIN_USERS"] = "Admin Only"

            response = client.post(
                "/schedule/2024-04-07/import",
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert (
                b"Only the first call resident or an admin can import schedules"
                in response.data
            )
        finally:
            os.environ["ADMIN_USERS"] = original_admin_users
            os.environ["USER_NAME"] = original_user_name

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
