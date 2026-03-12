"""Tests for anesthesia stop-time syncing."""

from datetime import date, datetime, time

import pytest

from backend.anesthesia_sync import (
    AnesthesiaStopRecord,
    AnesthesiaSyncResult,
    sync_anesthesia_stop_times,
)
from backend.models import Resident, Role, TimeEntry, db


def _resident(
    *,
    name: str,
    epic_id: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> Resident:
    resident = Resident(
        name=name,
        epic_id=epic_id,
        first_name=first_name,
        last_name=last_name,
        active=True,
    )
    db.session.add(resident)
    db.session.commit()
    return resident


def _role(name: str, *, is_call_team: bool = False) -> Role:
    role = Role(
        name=name,
        cutoff_hour=17,
        cutoff_minute=30,
        display_order=50,
        is_call_team=is_call_team,
    )
    db.session.add(role)
    db.session.commit()
    return role


def _entry(
    *,
    resident_id: int,
    role_id: int,
    work_date: date,
    exit_time_value: time | None = None,
    anesthesia_stop_time_value: time | None = None,
) -> TimeEntry:
    entry = TimeEntry(
        date=work_date,
        resident_id=resident_id,
        role_id=role_id,
        exit_time=exit_time_value,
        anesthesia_stop_time=anesthesia_stop_time_value,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


@pytest.mark.unit
class TestAnesthesiaSync:
    """Tests for syncing anesthesia stop times into time entries."""

    def test_sync_updates_blank_anesthesia_stop_time_by_provider_id(
        self, app, clean_database
    ):
        with app.app_context():
            resident = _resident(
                name="PATEL, SARAL B",
                epic_id="R124845",
                first_name="Saral",
                last_name="Patel",
            )
            role = _role("Anesthesia Sync Role")
            entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 4),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 4),
                date(2026, 3, 4),
                records=[
                    AnesthesiaStopRecord(
                        provider_id="R124845",
                        provider_name="PATEL, SARAL B",
                        work_date=date(2026, 3, 4),
                        stop_datetime=datetime(2026, 3, 4, 16, 11),
                    )
                ],
            )

            refreshed = db.session.get(TimeEntry, entry.id)
            assert refreshed is not None
            assert refreshed.exit_time is None
            assert refreshed.anesthesia_stop_time == time(16, 11)
            assert result.applied_updates == 1
            assert result.planned_updates == 1
            assert result.skipped_missing_entry == 0

            db.session.delete(refreshed)
            db.session.delete(role)
            db.session.delete(resident)
            db.session.commit()

    def test_sync_dry_run_does_not_write_changes(self, app, clean_database):
        with app.app_context():
            resident = _resident(name="LEE, ALEX", epic_id="R200001")
            role = _role("Dry Run Role")
            entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 5),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 5),
                date(2026, 3, 5),
                dry_run=True,
                records=[
                    AnesthesiaStopRecord(
                        provider_id="R200001",
                        provider_name="LEE, ALEX",
                        work_date=date(2026, 3, 5),
                        stop_datetime=datetime(2026, 3, 5, 18, 42),
                    )
                ],
            )

            refreshed = db.session.get(TimeEntry, entry.id)
            assert refreshed is not None
            assert refreshed.exit_time is None
            assert refreshed.anesthesia_stop_time is None
            assert result.dry_run is True
            assert result.planned_updates == 1
            assert result.applied_updates == 0

            db.session.delete(refreshed)
            db.session.delete(role)
            db.session.delete(resident)
            db.session.commit()

    def test_sync_skips_existing_anesthesia_stop_time_without_overwrite(
        self, app, clean_database
    ):
        with app.app_context():
            resident = _resident(name="KIM, JAMIE", epic_id="R200002")
            role = _role("Existing Exit Role")
            entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 6),
                anesthesia_stop_time_value=time(17, 45),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 6),
                date(2026, 3, 6),
                records=[
                    AnesthesiaStopRecord(
                        provider_id="R200002",
                        provider_name="KIM, JAMIE",
                        work_date=date(2026, 3, 6),
                        stop_datetime=datetime(2026, 3, 6, 19, 0),
                    )
                ],
            )

            refreshed = db.session.get(TimeEntry, entry.id)
            assert refreshed is not None
            assert refreshed.anesthesia_stop_time == time(17, 45)
            assert result.applied_updates == 0
            assert result.skipped_existing_stop_time == 1

            db.session.delete(refreshed)
            db.session.delete(role)
            db.session.delete(resident)
            db.session.commit()

    def test_sync_matches_by_name_when_provider_id_is_missing(
        self, app, clean_database
    ):
        with app.app_context():
            resident = _resident(
                name="Patel, Saral B",
                first_name="Saral",
                last_name="Patel",
            )
            role = _role("Name Match Role")
            entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 7),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 7),
                date(2026, 3, 7),
                records=[
                    AnesthesiaStopRecord(
                        provider_id=None,
                        provider_name="PATEL, SARAL B",
                        work_date=date(2026, 3, 7),
                        stop_datetime=datetime(2026, 3, 7, 20, 3),
                    )
                ],
            )

            refreshed = db.session.get(TimeEntry, entry.id)
            assert refreshed is not None
            assert refreshed.exit_time is None
            assert refreshed.anesthesia_stop_time == time(20, 3)
            assert result.applied_updates == 1
            assert result.matched_residents == 1

            db.session.delete(refreshed)
            db.session.delete(role)
            db.session.delete(resident)
            db.session.commit()

    def test_sync_skips_ambiguous_multiple_entries_for_same_day(
        self, app, clean_database
    ):
        with app.app_context():
            resident = _resident(name="BROWN, TAYLOR", epic_id="R200003")
            role_one = _role("Ambiguous Role One")
            role_two = _role("Ambiguous Role Two")
            first_entry = _entry(
                resident_id=resident.id,
                role_id=role_one.id,
                work_date=date(2026, 3, 8),
            )
            second_entry = _entry(
                resident_id=resident.id,
                role_id=role_two.id,
                work_date=date(2026, 3, 8),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 8),
                date(2026, 3, 8),
                records=[
                    AnesthesiaStopRecord(
                        provider_id="R200003",
                        provider_name="BROWN, TAYLOR",
                        work_date=date(2026, 3, 8),
                        stop_datetime=datetime(2026, 3, 8, 21, 5),
                    )
                ],
            )

            refreshed_first = db.session.get(TimeEntry, first_entry.id)
            refreshed_second = db.session.get(TimeEntry, second_entry.id)
            assert refreshed_first is not None
            assert refreshed_second is not None
            assert refreshed_first.exit_time is None
            assert refreshed_second.exit_time is None
            assert refreshed_first.anesthesia_stop_time is None
            assert refreshed_second.anesthesia_stop_time is None
            assert result.applied_updates == 0
            assert result.skipped_ambiguous_entry == 1

            db.session.delete(refreshed_first)
            db.session.delete(refreshed_second)
            db.session.delete(role_one)
            db.session.delete(role_two)
            db.session.delete(resident)
            db.session.commit()


@pytest.mark.unit
class TestAnesthesiaSyncCli:
    """Tests for the sync CLI command."""

    def test_cli_runs_sync_and_prints_summary(self, runner, monkeypatch):
        captured: dict[str, object] = {}

        def _fake_sync(*args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs
            return AnesthesiaSyncResult(
                fetched_records=2,
                matched_residents=2,
                planned_updates=1,
                applied_updates=1,
                unchanged_entries=1,
                skipped_missing_resident=0,
                skipped_ambiguous_resident=0,
                skipped_missing_entry=0,
                skipped_ambiguous_entry=0,
                skipped_existing_stop_time=0,
                dry_run=False,
            )

        monkeypatch.setattr(
            "backend.app.sync_anesthesia_stop_times",
            _fake_sync,
        )

        result = runner.invoke(
            args=[
                "sync-anesthesia-stop-times",
                "--start-date",
                "2026-03-01",
                "--end-date",
                "2026-03-07",
            ]
        )

        assert result.exit_code == 0
        assert "fetched 2 records" in result.output.casefold()
        assert captured["kwargs"] == {
            "start_date": date(2026, 3, 1),
            "end_date": date(2026, 3, 7),
            "overwrite_existing": False,
            "dry_run": False,
            "user": "Admin",
        }
