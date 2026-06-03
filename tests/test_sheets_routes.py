"""Tests for sheet routes."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest
import pytz
from sqlalchemy.exc import IntegrityError

from backend.models import AuditLog, DailySheet, Resident, Role, TimeEntry, db
from backend.utils import get_effective_date


def _restore_sheet_state(
    sheet_date,
    *,
    existed: bool,
    locked: bool | None = None,
    locked_by: str | None = None,
    locked_at=None,
) -> None:
    """Restore a sheet's original state or delete it if the test created it."""
    db.session.rollback()
    sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if sheet is None:
        return

    if not existed:
        db.session.delete(sheet)
    else:
        if locked is not None:
            sheet.locked = locked
        sheet.locked_by = locked_by
        sheet.locked_at = locked_at

    db.session.commit()


def _delete_entry(entry_id: int) -> None:
    """Delete a time entry by ID if it still exists."""
    entry = db.session.get(TimeEntry, entry_id)
    if entry is not None:
        db.session.delete(entry)


class TestSheetsIndex:
    """Tests for the sheets index page."""

    def test_index_creates_daily_sheet_if_not_exists(self, client, app):
        """Test that index creates daily sheet if it doesn't exist."""
        with app.app_context():
            today = get_effective_date()
            DailySheet.query.filter_by(date=today).delete()
            db.session.commit()

            try:
                response = client.get("/")
                assert response.status_code == 200

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
            finally:
                _restore_sheet_state(today, existed=False)

    def test_index_shows_roles(self, client, app, sample_role):
        """Test that index shows available roles."""
        with app.app_context():
            response = client.get("/")
            assert response.status_code == 200
            assert sample_role.name.encode() in response.data

    def test_index_shows_navigation_links(self, client):
        """Test that index shows navigation links."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Previous Day" in response.data
        assert b"Today" in response.data
        assert b"Next Day" in response.data

    def test_index_shows_lock_button(self, client):
        """Test that index shows lock/unlock button."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"Lock Sheet" in response.data or b"Unlock Sheet" in response.data

    def test_index_shows_import_button_for_regular_user(self, client, app, monkeypatch):
        """Regular users still see schedule import even without edit rights."""
        monkeypatch.setitem(app.config, "USER_NAME", "Regular User")
        monkeypatch.setitem(app.config, "ADMIN_USERS", "Admin Only")

        response = client.get("/")
        assert response.status_code == 200
        assert b"Import Schedule" in response.data
        assert b"Add New Entry" not in response.data
        assert b"Lock Sheet" not in response.data
        assert b"Unlock Sheet" not in response.data


class TestSheetsView:
    """Tests for viewing specific date sheets."""

    def test_view_past_date(self, client):
        """Test viewing a past date sheet."""
        past_date = get_effective_date() - timedelta(days=7)
        date_str = past_date.strftime("%Y-%m-%d")
        with client.application.app_context():
            sheet_existed = (
                DailySheet.query.filter_by(date=past_date).first() is not None
            )

        try:
            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200
            assert past_date.strftime("%B %d, %Y").encode() in response.data
        finally:
            with client.application.app_context():
                _restore_sheet_state(past_date, existed=sheet_existed)

    def test_view_future_date(self, client):
        """Test viewing a future date sheet."""
        future_date = get_effective_date() + timedelta(days=7)
        date_str = future_date.strftime("%Y-%m-%d")
        with client.application.app_context():
            sheet_existed = (
                DailySheet.query.filter_by(date=future_date).first() is not None
            )

        try:
            response = client.get(f"/sheets/{date_str}")
            assert response.status_code == 200
            assert future_date.strftime("%B %d, %Y").encode() in response.data
        finally:
            with client.application.app_context():
                _restore_sheet_state(future_date, existed=sheet_existed)

    def test_view_invalid_date_format(self, client):
        """Test viewing with invalid date format redirects."""
        response = client.get("/sheets/invalid-date", follow_redirects=True)
        assert response.status_code == 200
        assert b"Invalid date format" in response.data

    def test_view_creates_sheet_if_not_exists(self, client, app):
        """Test that viewing creates sheet if it doesn't exist."""
        with app.app_context():
            future_date = get_effective_date() + timedelta(days=100)
            date_str = future_date.strftime("%Y-%m-%d")

            DailySheet.query.filter_by(date=future_date).delete()
            db.session.commit()

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200

                sheet = DailySheet.query.filter_by(date=future_date).first()
                assert sheet is not None
            finally:
                _restore_sheet_state(future_date, existed=False)

    def test_view_shows_entries_for_date(
        self, client, app, sample_resident, sample_role
    ):
        """Test that view shows entries for the specific date."""
        with app.app_context():
            test_date = get_effective_date() - timedelta(days=5)
            date_str = test_date.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=test_date).first() is not None
            )

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200
                assert sample_resident.name.encode() in response.data
            finally:
                db.session.rollback()
                _delete_entry(entry_id)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=test_date).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()

    def test_view_shows_anesthesia_stop_time_column(
        self, client, app, sample_resident, sample_role
    ):
        """The ECC sheet shows the read-only anesthesia stop time column."""
        with app.app_context():
            test_date = get_effective_date() - timedelta(days=4)
            date_str = test_date.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=test_date).first() is not None
            )

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                anesthesia_stop_time=time(16, 11),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200
                assert b"Anes Stop" in response.data
                assert b"04:11 PM" in response.data
            finally:
                db.session.rollback()
                _delete_entry(entry_id)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=test_date).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()

    def test_view_footer_colspan_matches_weekday_columns(
        self, client, app, sample_resident, sample_role
    ):
        """Weekday totals should span the added anesthesia stop column."""
        with app.app_context():
            test_date = date(2026, 3, 9)
            date_str = test_date.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=test_date).first() is not None
            )

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                anesthesia_stop_time=time(16, 11),
                exit_time=time(18, 5),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200
                assert b'<td colspan="4">' in response.data
            finally:
                db.session.rollback()
                _delete_entry(entry_id)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=test_date).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()

    def test_view_footer_colspan_matches_weekend_columns(
        self, client, app, sample_resident, sample_role
    ):
        """Weekend totals should span the added anesthesia stop column."""
        with app.app_context():
            test_date = date(2026, 3, 8)
            date_str = test_date.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=test_date).first() is not None
            )

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=sample_role.id,
                anesthesia_stop_time=time(16, 11),
                exit_time=time(18, 5),
            )
            db.session.add(entry)
            db.session.commit()
            entry_id = entry.id

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200
                assert b'<td colspan="5">' in response.data
            finally:
                db.session.rollback()
                _delete_entry(entry_id)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=test_date).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()

    def test_auto_lock_warning_only_shows_on_previous_calendar_day(self, client, app):
        """The 8 AM banner should appear on the previous calendar day's sheet."""
        philly_tz = pytz.timezone("America/New_York")
        current_time = philly_tz.localize(datetime(2026, 3, 9, 8, 21))
        previous_date = current_time.date() - timedelta(days=1)
        current_date = current_time.date()

        with app.app_context():
            previous_sheet_existed = (
                DailySheet.query.filter_by(date=previous_date).first() is not None
            )
            current_sheet_existed = (
                DailySheet.query.filter_by(date=current_date).first() is not None
            )

        try:
            with patch(
                "backend.routes.sheets.get_philadelphia_time",
                return_value=current_time,
            ):
                previous_response = client.get("/sheets/2026-03-08")
                current_response = client.get("/sheets/2026-03-09")

            assert b"This sheet will auto-lock at 09:00 AM" in previous_response.data
            assert b"This sheet will auto-lock at 09:00 AM" not in current_response.data
        finally:
            with app.app_context():
                _restore_sheet_state(previous_date, existed=previous_sheet_existed)
                _restore_sheet_state(current_date, existed=current_sheet_existed)

    def test_view_renders_lock_confirmation_fallback_when_exit_times_missing(
        self, client, app, sample_resident
    ):
        """Lock confirmation metadata should be present even before JS initializes."""
        with app.app_context():
            test_date = get_effective_date() + timedelta(days=30)
            overtime_role = Role.query.filter_by(name="ECC 1").first()
            assert overtime_role is not None
            overtime_role_id = overtime_role.id

            sheet = DailySheet.query.filter_by(date=test_date).first()
            if sheet is None:
                sheet = DailySheet(date=test_date, locked=False)
                db.session.add(sheet)
            else:
                sheet.locked = False

            entry = TimeEntry(
                date=test_date,
                resident_id=sample_resident.id,
                role_id=overtime_role.id,
                exit_time=None,
            )
            db.session.add(entry)
            db.session.commit()
            db.session.remove()

        try:
            response = client.get(f"/sheets/{test_date.strftime('%Y-%m-%d')}")

            assert response.status_code == 200
            html = response.data.decode()
            lock_form_index = html.index('id="lock-sheet-form"')
            lock_form_markup = html[lock_form_index : lock_form_index + 800]

            assert "data-confirm-title=" in lock_form_markup
            assert "data-confirm-message=" in lock_form_markup
            assert (
                "These residents will not receive overtime credit:" in lock_form_markup
            )
            assert sample_resident.name in lock_form_markup
            assert html.count('class="btn-close"') >= 1
        finally:
            with app.app_context():
                persisted_entry = TimeEntry.query.filter_by(
                    date=test_date,
                    resident_id=sample_resident.id,
                    role_id=overtime_role_id,
                ).first()
                if persisted_entry is not None:
                    db.session.delete(persisted_entry)
                persisted_sheet = DailySheet.query.filter_by(date=test_date).first()
                if persisted_sheet is not None:
                    db.session.delete(persisted_sheet)
                db.session.commit()

    def test_overtime_entries_are_sorted_by_role_then_resident(self, client, app):
        """Manual overtime additions should render in role/name order."""
        with app.app_context():
            sheet_date = get_effective_date() - timedelta(days=10)
            date_str = sheet_date.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=sheet_date).first() is not None
            )

            residents = [
                Resident(name="Sort Order Held Resident", active=True),
                Resident(name="Sort Order Zebra Resident", active=True),
                Resident(name="Sort Order Alpha Resident", active=True),
            ]
            db.session.add_all(residents)
            db.session.commit()
            resident_ids = [resident.id for resident in residents]

            ecc_role = Role.query.filter_by(name="ECC 1").first()
            held_role = Role.query.filter_by(name="Held").first()
            assert ecc_role is not None
            assert held_role is not None

            entries = [
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[0].id,
                    role_id=held_role.id,
                ),
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[1].id,
                    role_id=ecc_role.id,
                ),
                TimeEntry(
                    date=sheet_date,
                    resident_id=residents[2].id,
                    role_id=ecc_role.id,
                ),
            ]
            db.session.add_all(entries)
            db.session.commit()
            entry_ids = [entry.id for entry in entries]

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200

                html = response.data.decode()
                alpha_index = html.index(f'id="entry-row-{entries[2].id}"')
                zebra_index = html.index(f'id="entry-row-{entries[1].id}"')
                held_index = html.index(f'id="entry-row-{entries[0].id}"')
                assert alpha_index < zebra_index < held_index
            finally:
                db.session.rollback()
                for entry_id in entry_ids:
                    _delete_entry(entry_id)
                for resident_id in resident_ids:
                    resident = db.session.get(Resident, resident_id)
                    if resident is not None:
                        db.session.delete(resident)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=sheet_date).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()


class TestSheetsLock:
    """Tests for locking/unlocking sheets."""

    def test_lock_unlocked_sheet(self, client, app):
        """Test locking an unlocked sheet."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if sheet:
                sheet.locked = False
                db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"locked" in response.data.lower()

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
                assert sheet.locked is True
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_unlock_locked_sheet(self, client, app):
        """Test unlocking a locked sheet."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"unlocked" in response.data.lower()

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
                assert sheet.locked is False
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_lock_records_user_and_time(self, client, app):
        """Test that locking records user and timestamp."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if sheet:
                sheet.locked = False
                sheet.locked_by = None
                sheet.locked_at = None
                db.session.commit()

            try:
                client.post(f"/sheets/{date_str}/lock", follow_redirects=True)

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
                assert sheet.locked is True
                assert sheet.locked_by is not None
                assert sheet.locked_at is not None
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_unlock_clears_user_and_time(self, client, app):
        """Test that unlocking clears user and timestamp."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=True)
                db.session.add(sheet)
            else:
                sheet.locked = True
            sheet.locked_by = "Test User"
            db.session.commit()

            try:
                client.post(f"/sheets/{date_str}/lock", follow_redirects=True)

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
                assert sheet.locked is False
                assert sheet.locked_by is None
                assert sheet.locked_at is None
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_lock_creates_sheet_if_not_exists(self, client, app):
        """Test that locking creates sheet if it doesn't exist."""
        with app.app_context():
            test_date = get_effective_date() - timedelta(days=200)
            date_str = test_date.strftime("%Y-%m-%d")
            audit_log_id = None

            DailySheet.query.filter_by(date=test_date).delete()
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=True,
                )
                assert response.status_code == 200

                sheet = DailySheet.query.filter_by(date=test_date).first()
                assert sheet is not None
                assert sheet.locked is True

                audit_log = (
                    AuditLog.query.filter_by(
                        action="LOCK",
                        entity_type="DailySheet",
                    )
                    .filter(AuditLog.details.contains(date_str))
                    .order_by(AuditLog.id.desc())
                    .first()
                )
                assert audit_log is not None
                audit_log_id = audit_log.id
            finally:
                db.session.rollback()
                if audit_log_id is not None:
                    audit_log = db.session.get(AuditLog, audit_log_id)
                    if audit_log is not None:
                        db.session.delete(audit_log)
                sheet = DailySheet.query.filter_by(date=test_date).first()
                if sheet is not None:
                    db.session.delete(sheet)
                db.session.commit()


class TestWeekendHolidayDisplay:
    """Tests for weekend/holiday display."""

    def test_weekend_indicated(self, client, app):
        """Test that weekends are indicated."""
        with app.app_context():
            today = get_effective_date()
            days_until_saturday = (5 - today.weekday()) % 7
            if days_until_saturday == 0:
                days_until_saturday = 7
            saturday = today + timedelta(days=days_until_saturday)
            date_str = saturday.strftime("%Y-%m-%d")
            sheet_existed = (
                DailySheet.query.filter_by(date=saturday).first() is not None
            )

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200
                data_lower = response.data.decode().lower()
                assert "weekend" in data_lower or "saturday" in data_lower
            finally:
                _restore_sheet_state(saturday, existed=sheet_existed)


class TestSheetsExceptionHandling:
    """Tests for exception handling in sheet routes."""

    def test_get_or_create_daily_sheet_returns_existing_sheet_after_race(self, app):
        """Concurrent insert races should fall back to the existing sheet."""
        import backend.routes.sheets as sheets_module

        with app.app_context():
            sheet_date = get_effective_date() + timedelta(days=500)
            existing_sheet = DailySheet(date=sheet_date)

            with (
                patch.object(sheets_module.DailySheet, "query") as mock_query,
                patch.object(
                    sheets_module.db.session,
                    "flush",
                    side_effect=IntegrityError("INSERT", {}, Exception("duplicate")),
                ),
            ):
                mock_query.filter_by.return_value.first.side_effect = [
                    None,
                    existing_sheet,
                ]

                sheet = sheets_module._get_or_create_daily_sheet(
                    sheet_date,
                    commit=False,
                )

            assert sheet is existing_sheet

    def test_get_or_create_daily_sheet_reraises_when_race_finds_no_sheet(self, app):
        """Integrity errors should bubble up when no existing sheet can be found."""
        import backend.routes.sheets as sheets_module

        with app.app_context():
            sheet_date = get_effective_date() + timedelta(days=501)

            with (
                patch.object(sheets_module.DailySheet, "query") as mock_query,
                patch.object(
                    sheets_module.db.session,
                    "flush",
                    side_effect=IntegrityError("INSERT", {}, Exception("duplicate")),
                ),
            ):
                mock_query.filter_by.return_value.first.side_effect = [None, None]

                with pytest.raises(IntegrityError):
                    sheets_module._get_or_create_daily_sheet(
                        sheet_date,
                        commit=False,
                    )

    def test_lock_sheet_db_error(self, client, app):
        """Test lock handles database errors gracefully."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
                db.session.commit()

            try:
                with patch.object(db.session, "commit") as mock_commit:
                    mock_commit.side_effect = Exception("Database error")

                    response = client.post(
                        f"/sheets/{date_str}/lock",
                        follow_redirects=True,
                    )
                    assert response.status_code == 200
                    assert b"error" in response.data.lower()
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_lock_invalid_date_redirects_to_index(self, client):
        """Invalid lock dates should redirect back to the dashboard."""
        response = client.post("/sheets/not-a-date/lock", follow_redirects=True)

        assert response.status_code == 200
        assert b"Invalid date format" in response.data

    def test_lock_sheet_get_or_create_error_flashes_generic_error(self, client, app):
        """Unexpected pre-audit lock failures should redirect with an error flash."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            with patch(
                "backend.routes.sheets._get_or_create_daily_sheet",
                side_effect=RuntimeError("boom"),
            ):
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=False,
                )

        assert response.status_code == 302

        follow_response = client.get(
            response.headers["Location"],
            follow_redirects=True,
        )
        assert follow_response.status_code == 200
        assert (
            b"An unexpected error occurred. Please try again." in follow_response.data
        )

    def test_lock_sheet_audit_failure_still_commits_lock(self, client, app):
        """Audit logging failures should not prevent the lock toggle."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
            else:
                sheet.locked = False
                sheet.locked_by = None
                sheet.locked_at = None
            db.session.commit()

            try:
                with patch(
                    "backend.routes.sheets.log_lock",
                    side_effect=RuntimeError("audit failed"),
                ):
                    response = client.post(
                        f"/sheets/{date_str}/lock",
                        follow_redirects=True,
                    )

                assert response.status_code == 200
                assert b"locked successfully" in response.data.lower()

                sheet = DailySheet.query.filter_by(date=today).first()
                assert sheet is not None
                assert sheet.locked is True
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )


class TestSheetLockPermissions:
    """Tests that lock/unlock requires first call or admin."""

    def test_lock_blocked_for_non_first_call(self, client, app, monkeypatch):
        """Non-admin, non-first-call user cannot lock/unlock the sheet."""
        monkeypatch.setitem(app.config, "USER_NAME", "Regular Viewer")
        monkeypatch.setitem(app.config, "ADMIN_USERS", "Admin Only")

        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
                db.session.commit()
            original_locked = sheet.locked

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    follow_redirects=True,
                )
                assert response.status_code == 200
                assert b"first call" in response.data.lower()

                db.session.refresh(sheet)
                assert sheet.locked == original_locked
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )


class TestCallTeamFiltering:
    """Tests for call-team role separation in the sheet context."""

    def test_call_team_entries_separated_from_overtime(self, client, app):
        """Call-team entries appear in call_team_entries, not overtime_entries."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")
            sheet_existed = DailySheet.query.filter_by(date=today).first() is not None

            for name in (
                "CT Filter Call Role",
                "CT Filter OT Role",
                "CT Filter Test Resident",
            ):
                existing_role = Role.query.filter_by(name=name).first()
                if existing_role:
                    db.session.delete(existing_role)
                existing_resident = Resident.query.filter_by(name=name).first()
                if existing_resident:
                    db.session.delete(existing_resident)
            db.session.commit()

            resident = Resident(name="CT Filter Test Resident", active=True)
            db.session.add(resident)

            call_role = Role(
                name="CT Filter Call Role",
                is_call_team=True,
                display_order=99,
            )
            ot_role = Role(
                name="CT Filter OT Role",
                is_call_team=False,
                display_order=100,
            )
            db.session.add_all([call_role, ot_role])
            db.session.commit()
            call_role_id = call_role.id
            ot_role_id = ot_role.id
            resident_id = resident.id

            call_entry = TimeEntry(
                date=today,
                resident_id=resident.id,
                role_id=call_role.id,
                exit_time=None,
            )
            ot_entry = TimeEntry(
                date=today,
                resident_id=resident.id,
                role_id=ot_role.id,
                exit_time=None,
            )
            db.session.add_all([call_entry, ot_entry])
            db.session.commit()
            call_entry_id = call_entry.id
            ot_entry_id = ot_entry.id

            try:
                response = client.get(f"/sheets/{date_str}")
                assert response.status_code == 200

                html = response.data.decode()
                assert "CT Filter Call Role:" in html, (
                    "Call-team role not in call-team section"
                )
                assert "CT Filter OT Role:" not in html, (
                    "OT role must not appear in call-team section"
                )
                assert "CT Filter OT Role" in html
            finally:
                db.session.rollback()
                _delete_entry(call_entry_id)
                _delete_entry(ot_entry_id)
                call_role = db.session.get(Role, call_role_id)
                ot_role = db.session.get(Role, ot_role_id)
                resident = db.session.get(Resident, resident_id)
                if call_role is not None:
                    db.session.delete(call_role)
                if ot_role is not None:
                    db.session.delete(ot_role)
                if resident is not None:
                    db.session.delete(resident)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=today).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()

    def test_call_team_roles_absent_from_overtime_roles(self, client, app):
        """Call-team roles must not appear in the overtime roles dropdown."""
        with app.app_context():
            today = get_effective_date()
            sheet_existed = DailySheet.query.filter_by(date=today).first() is not None
            call_role = Role(
                name="CT Dropdown Call Role",
                is_call_team=True,
                display_order=98,
            )
            db.session.add(call_role)
            db.session.commit()
            call_role_id = call_role.id

            try:
                response = client.get("/")
                assert response.status_code == 200
                assert b"CT Dropdown Call Role" not in response.data
            finally:
                db.session.rollback()
                call_role = db.session.get(Role, call_role_id)
                if call_role is not None:
                    db.session.delete(call_role)
                if not sheet_existed:
                    sheet = DailySheet.query.filter_by(date=today).first()
                    if sheet is not None:
                        db.session.delete(sheet)
                db.session.commit()


class TestSheetLockJsonResponse:
    """Tests that the lock route returns JSON when requested via Accept header."""

    def test_lock_returns_json_when_accept_json(self, client, app):
        """Lock route returns JSON payload with success/locked/locked_by/locked_at."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
            else:
                sheet.locked = False
                sheet.locked_by = None
                sheet.locked_at = None
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    headers={
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                assert response.status_code == 200
                assert response.content_type == "application/json"

                payload = response.get_json()
                assert payload is not None
                assert payload["success"] is True
                assert "locked" in payload
                assert "message" in payload
                # locked_by and locked_at present when locked
                if payload["locked"]:
                    assert "locked_by" in payload
                    assert "locked_at" in payload
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_unlock_returns_json_when_accept_json(self, client, app):
        """Unlock route returns JSON payload with locked=False and null locked_by."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=True, locked_by="Admin")
                db.session.add(sheet)
            else:
                sheet.locked = True
                sheet.locked_by = "Admin"
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    headers={
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                assert response.status_code == 200
                payload = response.get_json()
                assert payload["success"] is True
                assert payload["locked"] is False
                assert payload["locked_by"] is None
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_lock_json_returns_500_on_db_error(self, client, app):
        """Lock route returns JSON 500 when a database error occurs."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None

            try:
                with patch.object(db.session, "commit") as mock_commit:
                    mock_commit.side_effect = Exception("DB error")
                    response = client.post(
                        f"/sheets/{date_str}/lock",
                        headers={
                            "Accept": "application/json",
                            "X-Requested-With": "XMLHttpRequest",
                        },
                    )
                assert response.status_code == 500
                payload = response.get_json()
                assert payload["success"] is False
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_lock_json_includes_show_import_button_false_when_locked(self, client, app):
        """Lock JSON response includes show_import_button=False when sheet is locked."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=False)
                db.session.add(sheet)
            else:
                sheet.locked = False
                sheet.locked_by = None
                sheet.locked_at = None
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    headers={
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                payload = response.get_json()
                assert payload["success"] is True
                assert payload["locked"] is True
                assert payload["show_import_button"] is False
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )

    def test_unlock_json_includes_show_import_button_true_when_unlocked(
        self, client, app
    ):
        """Unlock JSON response includes show_import_button=True when sheet is
        unlocked."""
        with app.app_context():
            today = get_effective_date()
            date_str = today.strftime("%Y-%m-%d")

            sheet = DailySheet.query.filter_by(date=today).first()
            sheet_existed = sheet is not None
            original_locked = sheet.locked if sheet else False
            original_locked_by = sheet.locked_by if sheet else None
            original_locked_at = sheet.locked_at if sheet else None
            if not sheet:
                sheet = DailySheet(date=today, locked=True, locked_by="Admin")
                db.session.add(sheet)
            else:
                sheet.locked = True
                sheet.locked_by = "Admin"
            db.session.commit()

            try:
                response = client.post(
                    f"/sheets/{date_str}/lock",
                    headers={
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                )
                payload = response.get_json()
                assert payload["success"] is True
                assert payload["locked"] is False
                assert payload["show_import_button"] is True
            finally:
                _restore_sheet_state(
                    today,
                    existed=sheet_existed,
                    locked=original_locked,
                    locked_by=original_locked_by,
                    locked_at=original_locked_at,
                )
