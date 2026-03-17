"""Tests for anesthesia stop-time syncing."""

import math
from datetime import date, datetime, time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import backend.anesthesia_sync as sync_module
from backend.anesthesia_sync import (
    AnesthesiaStopRecord,
    AnesthesiaSyncResult,
    sync_anesthesia_stop_times,
)
from backend.models import AuditLog, Resident, Role, TimeEntry, db


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
class TestAnesthesiaSyncHelpers:
    """Focused unit coverage for anesthesia-sync helper logic."""

    def test_config_helpers_validate_and_default_values(self, app):
        with app.app_context():
            original_connection = app.config.get("ANESTHESIA_SQL_CONNECTION_STRING")
            original_table = app.config.get("ANESTHESIA_SQL_SOURCE_TABLE")
            original_provider_type = app.config.get("ANESTHESIA_SQL_PROVIDER_TYPE")
            original_timeout = app.config.get("ANESTHESIA_SQL_TIMEOUT")
            try:
                app.config["ANESTHESIA_SQL_CONNECTION_STRING"] = " Driver=test "
                app.config["ANESTHESIA_SQL_SOURCE_TABLE"] = "dbo.Valid_Table"
                app.config["ANESTHESIA_SQL_PROVIDER_TYPE"] = ""
                app.config["ANESTHESIA_SQL_TIMEOUT"] = None

                config_value = sync_module._config_value(
                    "ANESTHESIA_SQL_CONNECTION_STRING"
                )
                assert config_value == " Driver=test "
                assert sync_module._connection_string() == "Driver=test"
                assert sync_module._source_table() == "dbo.Valid_Table"
                assert sync_module._provider_type() == "Anes Resident"
                assert sync_module._query_timeout() == 30
            finally:
                app.config["ANESTHESIA_SQL_CONNECTION_STRING"] = original_connection
                app.config["ANESTHESIA_SQL_SOURCE_TABLE"] = original_table
                app.config["ANESTHESIA_SQL_PROVIDER_TYPE"] = original_provider_type
                app.config["ANESTHESIA_SQL_TIMEOUT"] = original_timeout

    def test_connection_string_raises_when_missing(self):
        with (
            patch.object(sync_module, "_config_value", return_value="   "),
            pytest.raises(
                sync_module.AnesthesiaSyncConfigError,
                match="ANESTHESIA_SQL_CONNECTION_STRING",
            ),
        ):
            sync_module._connection_string()

    def test_source_table_rejects_missing_and_invalid_values(self):
        with (
            patch.object(sync_module, "_config_value", return_value=""),
            pytest.raises(
                sync_module.AnesthesiaSyncConfigError,
                match="ANESTHESIA_SQL_SOURCE_TABLE is not configured",
            ),
        ):
            sync_module._source_table()

        with (
            patch.object(
                sync_module,
                "_config_value",
                return_value="dbo.bad-table;",
            ),
            pytest.raises(
                sync_module.AnesthesiaSyncConfigError,
                match="may only contain letters, numbers",
            ),
        ):
            sync_module._source_table()

    def test_provider_type_and_timeout_use_explicit_config_without_app_context(self):
        with (
            patch.object(
                sync_module.Config,
                "ANESTHESIA_SQL_PROVIDER_TYPE",
                "Override",
            ),
            patch.object(sync_module.Config, "ANESTHESIA_SQL_TIMEOUT", 45),
        ):
            assert sync_module._provider_type() == "Override"
            assert sync_module._query_timeout() == 45

    def test_build_stop_time_query_uses_validated_source_table(self):
        with patch.object(sync_module, "_source_table", return_value="dbo.StopView"):
            query = sync_module._build_stop_time_query()

        assert "FROM dbo.StopView" in query
        assert "ProviderType = ?" in query
        assert "ORDER BY WorkDate ASC, ProviderName ASC" in query

    def test_load_pyodbc_raises_dependency_error(self):
        with (
            patch.object(
                sync_module.importlib,
                "import_module",
                side_effect=ModuleNotFoundError("pyodbc"),
            ),
            pytest.raises(
                sync_module.AnesthesiaSyncDependencyError,
                match="pyodbc is not installed",
            ),
        ):
            sync_module._load_pyodbc()

    def test_row_mapping_and_value_coercion_helpers(self):
        assert sync_module._row_to_mapping(["a", "b"], [1]) == {"a": 1}
        assert sync_module._coerce_date(
            datetime(2026, 3, 1, 10, 30),
            field_name="WorkDate",
        ) == date(2026, 3, 1)
        assert sync_module._coerce_date(
            "2026-03-01 08:00:00",
            field_name="WorkDate",
        ) == date(2026, 3, 1)
        assert sync_module._coerce_datetime(
            "2026-03-01 16:11:00",
            field_name="StopDateTime",
        ) == datetime(2026, 3, 1, 16, 11)

        with pytest.raises(sync_module.AnesthesiaSyncError, match="Invalid WorkDate"):
            sync_module._coerce_date("not-a-date", field_name="WorkDate")

        with pytest.raises(
            sync_module.AnesthesiaSyncError,
            match="Unsupported WorkDate type",
        ):
            sync_module._coerce_date(math.pi, field_name="WorkDate")

        with pytest.raises(
            sync_module.AnesthesiaSyncError,
            match="Invalid StopDateTime",
        ):
            sync_module._coerce_datetime("not-a-datetime", field_name="StopDateTime")

        with pytest.raises(
            sync_module.AnesthesiaSyncError,
            match="Unsupported StopDateTime type",
        ):
            sync_module._coerce_datetime(7, field_name="StopDateTime")

    def test_record_from_row_normalizes_provider_fields(self):
        record = sync_module._record_from_row(
            {
                "ProviderID": " R123 ",
                "ProviderName": "  PATEL, SARAL B  ",
                "WorkDate": "2026-03-04 00:00:00",
                "StopDateTime": "2026-03-04 16:11:59",
            }
        )

        assert record.provider_id == "R123"
        assert record.provider_name == "PATEL, SARAL B"
        assert record.work_date == date(2026, 3, 4)
        assert record.stop_time == time(16, 11)

    def test_fetch_anesthesia_stop_records_success(self):
        class _Cursor:
            description = (
                ("ProviderID",),
                ("ProviderName",),
                ("WorkDate",),
                ("StopDateTime",),
            )

            def __init__(self) -> None:
                self.executed: tuple | None = None

            def execute(self, *args) -> None:
                self.executed = args

            @staticmethod
            def fetchall():
                return [
                    (
                        "R123",
                        "PATEL, SARAL B",
                        date(2026, 3, 4),
                        datetime(2026, 3, 4, 16, 11),
                    )
                ]

        class _Connection:
            def __init__(self) -> None:
                self.cursor_obj = _Cursor()
                self.closed = False

            def cursor(self):
                return self.cursor_obj

            def close(self) -> None:
                self.closed = True

        connection = _Connection()
        fake_pyodbc = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)

        with (
            patch.object(sync_module, "_load_pyodbc", return_value=fake_pyodbc),
            patch.object(sync_module, "_connection_string", return_value="Driver=test"),
            patch.object(sync_module, "_query_timeout", return_value=15),
            patch.object(
                sync_module,
                "_build_stop_time_query",
                return_value="SELECT 1",
            ),
            patch.object(sync_module, "_provider_type", return_value="Anes Resident"),
        ):
            records = sync_module.fetch_anesthesia_stop_records(
                date(2026, 3, 4),
                date(2026, 3, 4),
            )

        assert len(records) == 1
        assert records[0].provider_id == "R123"
        assert connection.cursor_obj.executed == (
            "SELECT 1",
            "Anes Resident",
            date(2026, 3, 4),
            date(2026, 3, 4),
        )
        assert connection.closed is True

    def test_fetch_anesthesia_stop_records_wraps_connection_and_query_errors(self):
        def _raise_connect(*_args, **_kwargs):
            raise Exception("connect")

        fake_pyodbc = SimpleNamespace(connect=_raise_connect)

        with (
            patch.object(sync_module, "_load_pyodbc", return_value=fake_pyodbc),
            patch.object(sync_module, "_connection_string", return_value="Driver=test"),
            patch.object(sync_module, "_query_timeout", return_value=15),
            pytest.raises(
                sync_module.AnesthesiaSyncError,
                match="Failed to connect to the anesthesia MSSQL source",
            ),
        ):
            sync_module.fetch_anesthesia_stop_records(
                date(2026, 3, 4),
                date(2026, 3, 4),
            )

        class _BrokenCursor:
            description = (("ProviderID",),)

            @staticmethod
            def execute(*_args) -> None:
                raise Exception("query")

        class _BrokenConnection:
            def __init__(self) -> None:
                self.closed = False

            @staticmethod
            def cursor():
                return _BrokenCursor()

            def close(self) -> None:
                self.closed = True

        broken_connection = _BrokenConnection()
        fake_pyodbc = SimpleNamespace(
            connect=lambda *_args, **_kwargs: broken_connection
        )

        with (
            patch.object(sync_module, "_load_pyodbc", return_value=fake_pyodbc),
            patch.object(sync_module, "_connection_string", return_value="Driver=test"),
            patch.object(sync_module, "_query_timeout", return_value=15),
            patch.object(
                sync_module,
                "_build_stop_time_query",
                return_value="SELECT 1",
            ),
            patch.object(sync_module, "_provider_type", return_value="Anes Resident"),
            pytest.raises(
                sync_module.AnesthesiaSyncError,
                match="Failed to query anesthesia stop times",
            ),
        ):
            sync_module.fetch_anesthesia_stop_records(
                date(2026, 3, 4),
                date(2026, 3, 4),
            )

        assert broken_connection.closed is True

    def test_fetch_anesthesia_stop_records_reraises_row_conversion_errors(self):
        class _Cursor:
            description = (("ProviderID",),)

            @staticmethod
            def execute(*_args) -> None:
                return None

            @staticmethod
            def fetchall():
                return [("R123",)]

        class _Connection:
            def __init__(self) -> None:
                self.closed = False

            @staticmethod
            def cursor():
                return _Cursor()

            def close(self) -> None:
                self.closed = True

        connection = _Connection()
        fake_pyodbc = SimpleNamespace(connect=lambda *_args, **_kwargs: connection)

        with (
            patch.object(sync_module, "_load_pyodbc", return_value=fake_pyodbc),
            patch.object(sync_module, "_connection_string", return_value="Driver=test"),
            patch.object(sync_module, "_query_timeout", return_value=15),
            patch.object(
                sync_module,
                "_build_stop_time_query",
                return_value="SELECT 1",
            ),
            patch.object(sync_module, "_provider_type", return_value="Anes Resident"),
            patch.object(
                sync_module,
                "_record_from_row",
                side_effect=sync_module.AnesthesiaSyncError("bad row"),
            ),
            pytest.raises(sync_module.AnesthesiaSyncError, match="bad row"),
        ):
            sync_module.fetch_anesthesia_stop_records(
                date(2026, 3, 4),
                date(2026, 3, 4),
            )

        assert connection.closed is True

    def test_name_lookup_helpers_cover_common_formats(self):
        assert sync_module._normalize_identifier(" R123 ") == "r123"
        assert sync_module._normalize_identifier("   ") is None
        assert sync_module._normalize_name("  Patel   Saral B ") == "patel saral b"
        assert sync_module._name_keys("PATEL, SARAL B") >= {
            "patel, saral b",
            "patel, saral",
            "saral patel",
        }
        assert sync_module._name_keys("  ") == set()

    def test_register_lookup_and_build_resident_lookups_mark_ambiguity(
        self, app, clean_database
    ):
        with app.app_context():
            lookup: dict[str, Resident | object] = {}
            first = _resident(name="Lookup One", epic_id="RID1")
            second = _resident(name="Lookup Two", epic_id="RID2")

            sync_module._register_lookup(lookup, None, first)
            sync_module._register_lookup(lookup, "rid1", first)
            sync_module._register_lookup(lookup, "rid1", first)
            sync_module._register_lookup(lookup, "rid1", second)
            assert lookup["rid1"] is sync_module._AMBIGUOUS

            ambiguous_one = _resident(
                name="PATEL, SARAL",
                epic_id="RID3",
                first_name="Saral",
                last_name="Patel",
            )
            ambiguous_two = _resident(
                name="Saral Patel",
                epic_id="RID4",
                first_name="Saral",
                last_name="Patel",
            )

            by_identifier, by_name = sync_module._build_resident_lookups()
            assert by_identifier["rid3"] is ambiguous_one
            assert by_identifier["rid4"] is ambiguous_two
            assert by_name["saral patel"] is sync_module._AMBIGUOUS

            for resident in (first, second, ambiguous_one, ambiguous_two):
                db.session.delete(resident)
            db.session.commit()

    def test_build_entry_lookup_and_stop_record_source_selection(
        self, app, clean_database
    ):
        with app.app_context():
            resident = _resident(name="Lookup Resident", epic_id="LOOKUP1")
            role = _role("Lookup Role")
            first_entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 10),
            )
            second_entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 11),
            )

            lookup = sync_module._build_entry_lookup(
                date(2026, 3, 10),
                date(2026, 3, 11),
            )
            assert lookup[resident.id, date(2026, 3, 10)][0].id == first_entry.id
            assert lookup[resident.id, date(2026, 3, 11)][0].id == second_entry.id

            provided = [
                AnesthesiaStopRecord(
                    provider_id="LOOKUP1",
                    provider_name="Lookup Resident",
                    work_date=date(2026, 3, 10),
                    stop_datetime=datetime(2026, 3, 10, 17, 0),
                )
            ]
            assert (
                sync_module._stop_records_for_sync(
                    date(2026, 3, 10),
                    date(2026, 3, 10),
                    records=provided,
                )
                == provided
            )

            with patch.object(
                sync_module,
                "fetch_anesthesia_stop_records",
                return_value=provided,
            ) as mock_fetch:
                assert (
                    sync_module._stop_records_for_sync(
                        date(2026, 3, 10),
                        date(2026, 3, 10),
                        records=None,
                    )
                    == provided
                )
            mock_fetch.assert_called_once_with(date(2026, 3, 10), date(2026, 3, 10))

            for entry in (first_entry, second_entry):
                persisted_entry = db.session.get(TimeEntry, entry.id)
                assert persisted_entry is not None
                db.session.delete(persisted_entry)
            db.session.delete(role)
            db.session.delete(resident)
            db.session.commit()

    def test_match_resident_and_choose_target_entry_helpers(self, app, clean_database):
        with app.app_context():
            resident = _resident(name="PATEL, SARAL", epic_id="RID5")
            alternate_resident = _resident(name="SARAL PATEL", epic_id="RID6")

            record = AnesthesiaStopRecord(
                provider_id="RID5",
                provider_name="PATEL, SARAL",
                work_date=date(2026, 3, 12),
                stop_datetime=datetime(2026, 3, 12, 18, 0),
            )
            matched, status = sync_module._match_resident(
                record,
                by_identifier={"rid5": resident},
                by_name={},
            )
            assert matched is resident
            assert status == "identifier"

            matched, status = sync_module._match_resident(
                record,
                by_identifier={"rid5": sync_module._AMBIGUOUS},
                by_name={},
            )
            assert matched is None
            assert status == "ambiguous"

            matched, status = sync_module._match_resident(
                AnesthesiaStopRecord(
                    provider_id=None,
                    provider_name="PATEL, SARAL",
                    work_date=date(2026, 3, 12),
                    stop_datetime=datetime(2026, 3, 12, 18, 0),
                ),
                by_identifier={},
                by_name={
                    "patel, saral": resident,
                    "saral patel": alternate_resident,
                },
            )
            assert matched is None
            assert status == "ambiguous"

            matched, status = sync_module._match_resident(
                AnesthesiaStopRecord(
                    provider_id=None,
                    provider_name="PATEL, SARAL",
                    work_date=date(2026, 3, 12),
                    stop_datetime=datetime(2026, 3, 12, 18, 0),
                ),
                by_identifier={},
                by_name={"patel, saral": resident},
            )
            assert matched is resident
            assert status == "name"

            matched, status = sync_module._match_resident(
                AnesthesiaStopRecord(
                    provider_id=None,
                    provider_name="PATEL, SARAL",
                    work_date=date(2026, 3, 12),
                    stop_datetime=datetime(2026, 3, 12, 18, 0),
                ),
                by_identifier={},
                by_name={"patel, saral": sync_module._AMBIGUOUS},
            )
            assert matched is None
            assert status == "ambiguous"

            matched, status = sync_module._match_resident(
                AnesthesiaStopRecord(
                    provider_id=None,
                    provider_name="UNKNOWN",
                    work_date=date(2026, 3, 12),
                    stop_datetime=datetime(2026, 3, 12, 18, 0),
                ),
                by_identifier={},
                by_name={},
            )
            assert matched is None
            assert status == "missing"

            non_call_team_entry = SimpleNamespace(
                role=SimpleNamespace(is_call_team=False),
                anesthesia_stop_time=None,
            )
            call_team_entry = SimpleNamespace(
                role=SimpleNamespace(is_call_team=True),
                anesthesia_stop_time=None,
            )
            populated_entry = SimpleNamespace(
                role=SimpleNamespace(is_call_team=False),
                anesthesia_stop_time=time(17, 0),
            )

            assert (
                sync_module._choose_target_entry(
                    [non_call_team_entry],
                    overwrite_existing=False,
                )
                is non_call_team_entry
            )
            assert (
                sync_module._choose_target_entry(
                    [call_team_entry],
                    overwrite_existing=False,
                )
                is call_team_entry
            )
            assert (
                sync_module._choose_target_entry(
                    [populated_entry, non_call_team_entry],
                    overwrite_existing=False,
                )
                is non_call_team_entry
            )
            assert (
                sync_module._choose_target_entry(
                    [populated_entry, non_call_team_entry],
                    overwrite_existing=True,
                )
                is None
            )

            db.session.delete(alternate_resident)
            db.session.delete(resident)
            db.session.commit()

    def test_process_record_and_persist_updates_edge_cases(self):
        record = AnesthesiaStopRecord(
            provider_id="RIDX",
            provider_name="PATEL, SARAL",
            work_date=date(2026, 3, 13),
            stop_datetime=datetime(2026, 3, 13, 18, 15),
        )

        resident = Resident(id=1, name="PATEL, SARAL", epic_id="RIDX", active=True)
        pending_updates: list[sync_module._PendingAuditUpdate] = []

        missing_resident_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={},
                by_name={},
                entries_by_key={},
                overwrite_existing=False,
                dry_run=False,
            ),
            stats=missing_resident_stats,
            pending_updates=pending_updates,
        )
        assert missing_resident_stats.skipped_missing_resident == 1

        ambiguous_resident_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={"ridx": sync_module._AMBIGUOUS},
                by_name={},
                entries_by_key={},
                overwrite_existing=False,
                dry_run=False,
            ),
            stats=ambiguous_resident_stats,
            pending_updates=pending_updates,
        )
        assert ambiguous_resident_stats.skipped_ambiguous_resident == 1

        missing_entry_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={"ridx": resident},
                by_name={},
                entries_by_key={},
                overwrite_existing=False,
                dry_run=False,
            ),
            stats=missing_entry_stats,
            pending_updates=pending_updates,
        )
        assert missing_entry_stats.skipped_missing_entry == 1

        existing_stop_entry = SimpleNamespace(
            anesthesia_stop_time=record.stop_time,
            role=SimpleNamespace(is_call_team=False),
        )
        unchanged_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={"ridx": resident},
                by_name={},
                entries_by_key={(1, record.work_date): [existing_stop_entry]},
                overwrite_existing=False,
                dry_run=False,
            ),
            stats=unchanged_stats,
            pending_updates=pending_updates,
        )
        assert unchanged_stats.unchanged_entries == 1

        existing_nonmatching_entry = SimpleNamespace(
            anesthesia_stop_time=time(17, 0),
            role=SimpleNamespace(is_call_team=False),
        )
        existing_stop_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={"ridx": resident},
                by_name={},
                entries_by_key={(1, record.work_date): [existing_nonmatching_entry]},
                overwrite_existing=False,
                dry_run=False,
            ),
            stats=existing_stop_stats,
            pending_updates=pending_updates,
        )
        assert existing_stop_stats.skipped_existing_stop_time == 1

        dry_run_entry = SimpleNamespace(
            anesthesia_stop_time=None,
            role=SimpleNamespace(is_call_team=False),
        )
        dry_run_stats = sync_module._SyncStats()
        sync_module._process_record(
            record,
            context=sync_module._SyncContext(
                by_identifier={"ridx": resident},
                by_name={},
                entries_by_key={(1, record.work_date): [dry_run_entry]},
                overwrite_existing=False,
                dry_run=True,
            ),
            stats=dry_run_stats,
            pending_updates=pending_updates,
        )
        assert dry_run_stats.planned_updates == 1
        assert pending_updates == []

        pending_update = sync_module._PendingAuditUpdate(
            entry=SimpleNamespace(
                id=99,
                resident_id=1,
                resident=SimpleNamespace(name="PATEL, SARAL"),
                role=SimpleNamespace(name="ECC 1"),
                date=record.work_date,
                anesthesia_stop_time=record.stop_time,
            ),
            old_stop_time=None,
            record=record,
        )
        result = AnesthesiaSyncResult(
            fetched_records=1,
            matched_residents=1,
            planned_updates=1,
            applied_updates=1,
            unchanged_entries=0,
            skipped_missing_resident=0,
            skipped_ambiguous_resident=0,
            skipped_missing_entry=0,
            skipped_ambiguous_entry=0,
            skipped_existing_stop_time=0,
            dry_run=False,
        )

        with (
            patch.object(
                sync_module,
                "log_update_strict",
                side_effect=RuntimeError("audit failed"),
            ),
            patch("backend.db_session.db.session.rollback") as mock_rollback,
            pytest.raises(RuntimeError, match="audit failed"),
        ):
            sync_module._persist_updates(
                [pending_update],
                result=result,
                user="sync-user",
            )

        mock_rollback.assert_called_once_with()

    def test_sync_rejects_inverted_date_ranges(self):
        with pytest.raises(
            sync_module.AnesthesiaSyncError,
            match="end_date must be on or after start_date",
        ):
            sync_module.sync_anesthesia_stop_times(
                date(2026, 3, 14),
                date(2026, 3, 13),
                records=[],
            )


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

    def test_sync_update_audit_uses_explicit_user(self, app, clean_database):
        with app.app_context():
            resident = _resident(name="NGUYEN, CASEY", epic_id="R200004")
            role = _role("Audit Attribution Role")
            entry = _entry(
                resident_id=resident.id,
                role_id=role.id,
                work_date=date(2026, 3, 9),
            )

            result = sync_anesthesia_stop_times(
                date(2026, 3, 9),
                date(2026, 3, 9),
                user="anesthesia-auto-sync",
                records=[
                    AnesthesiaStopRecord(
                        provider_id="R200004",
                        provider_name="NGUYEN, CASEY",
                        work_date=date(2026, 3, 9),
                        stop_datetime=datetime(2026, 3, 9, 18, 5),
                    )
                ],
            )

            assert result.applied_updates == 1
            update_log = AuditLog.query.filter_by(
                action="UPDATE",
                entity_type="TimeEntry",
                entity_id=entry.id,
                user="anesthesia-auto-sync",
            ).first()
            import_log = AuditLog.query.filter_by(
                action="IMPORT",
                entity_type="anesthesia_stop_sync",
                user="anesthesia-auto-sync",
            ).first()
            assert update_log is not None
            assert import_log is not None

            db.session.delete(update_log)
            db.session.delete(import_log)
            refreshed = db.session.get(TimeEntry, entry.id)
            assert refreshed is not None
            db.session.delete(refreshed)
            db.session.delete(role)
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
