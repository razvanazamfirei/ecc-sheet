"""Sync anesthesia stop times from an external Microsoft SQL Server source."""

from __future__ import annotations

import importlib
import logging
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Final

from flask import current_app, has_app_context
from sqlalchemy.orm import joinedload

from .audit import log_import_strict, log_update_strict
from .config import Config
from .models import Resident, TimeEntry, db

logger = logging.getLogger(__name__)

_AMBIGUOUS: Final = object()
_SAFE_SOURCE_RE: Final = re.compile(r"^[A-Za-z0-9_.\[\]]+$")
_WORK_DATE_SQL: Final = (
    "CAST(COALESCE(SCHED_START_TIME, DutyStarted, ANESTHESIA_STOP_EVENTTIME) AS date)"
)


class AnesthesiaSyncError(RuntimeError):
    """Base error raised by the anesthesia stop-time sync."""


class AnesthesiaSyncConfigError(AnesthesiaSyncError):
    """Raised when required MSSQL sync configuration is missing or invalid."""


class AnesthesiaSyncDependencyError(AnesthesiaSyncError):
    """Raised when the optional MSSQL dependency is unavailable."""


@dataclass(frozen=True)
class AnesthesiaStopRecord:
    """Latest anesthesia stop time for a provider on a single work date."""

    provider_id: str | None
    provider_name: str
    work_date: date
    stop_datetime: datetime

    @property
    def stop_time(self) -> time:
        """Return the stop time truncated to minute precision."""
        return time(self.stop_datetime.hour, self.stop_datetime.minute)


@dataclass(frozen=True)
class AnesthesiaSyncResult:
    """Summary of a stop-time sync run."""

    fetched_records: int
    matched_residents: int
    planned_updates: int
    applied_updates: int
    unchanged_entries: int
    skipped_missing_resident: int
    skipped_ambiguous_resident: int
    skipped_missing_entry: int
    skipped_ambiguous_entry: int
    skipped_existing_stop_time: int
    dry_run: bool

    def summary(self) -> str:
        """Return a compact human-readable summary."""
        action = "Would update" if self.dry_run else "Updated"
        count = self.planned_updates if self.dry_run else self.applied_updates
        return (
            f"Fetched {self.fetched_records} records; matched {self.matched_residents} "
            f"residents; {action.lower()} {count} entries; unchanged "
            f"{self.unchanged_entries}; missing residents "
            f"{self.skipped_missing_resident}; ambiguous residents "
            f"{self.skipped_ambiguous_resident}; missing entries "
            f"{self.skipped_missing_entry}; ambiguous entries "
            f"{self.skipped_ambiguous_entry}; skipped existing anesthesia stop times "
            f"{self.skipped_existing_stop_time}."
        )


type ResidentLookup = dict[str, Resident | object]
type EntryLookup = dict[tuple[int, date], list[TimeEntry]]


@dataclass
class _SyncStats:
    """Mutable counters used while processing stop-time records."""

    matched_residents: int = 0
    planned_updates: int = 0
    applied_updates: int = 0
    unchanged_entries: int = 0
    skipped_missing_resident: int = 0
    skipped_ambiguous_resident: int = 0
    skipped_missing_entry: int = 0
    skipped_ambiguous_entry: int = 0
    skipped_existing_stop_time: int = 0

    def to_result(self, *, fetched_records: int, dry_run: bool) -> AnesthesiaSyncResult:
        """Freeze the mutable counters into the public result object."""
        return AnesthesiaSyncResult(
            fetched_records=fetched_records,
            matched_residents=self.matched_residents,
            planned_updates=self.planned_updates,
            applied_updates=self.applied_updates,
            unchanged_entries=self.unchanged_entries,
            skipped_missing_resident=self.skipped_missing_resident,
            skipped_ambiguous_resident=self.skipped_ambiguous_resident,
            skipped_missing_entry=self.skipped_missing_entry,
            skipped_ambiguous_entry=self.skipped_ambiguous_entry,
            skipped_existing_stop_time=self.skipped_existing_stop_time,
            dry_run=dry_run,
        )


@dataclass(frozen=True)
class _PendingAuditUpdate:
    """Time-entry mutation to persist and audit after record processing."""

    entry: TimeEntry
    old_stop_time: time | None
    record: AnesthesiaStopRecord


@dataclass(frozen=True)
class _SyncContext:
    """Shared lookup state for processing a batch of stop-time records."""

    by_identifier: ResidentLookup
    by_name: ResidentLookup
    entries_by_key: EntryLookup
    overwrite_existing: bool
    dry_run: bool


def _config_value(name: str) -> Any:
    """Read runtime configuration from the Flask app when available."""
    if has_app_context():
        return current_app.config.get(name, getattr(Config, name, None))
    return getattr(Config, name, None)


def _connection_string() -> str:
    """Return the configured ODBC connection string."""
    connection_string = str(
        _config_value("ANESTHESIA_SQL_CONNECTION_STRING") or ""
    ).strip()
    if not connection_string:
        raise AnesthesiaSyncConfigError(
            "ANESTHESIA_SQL_CONNECTION_STRING is not configured."
        )
    return connection_string


def _source_table() -> str:
    """Return the configured MSSQL source table or view."""
    source_table = str(_config_value("ANESTHESIA_SQL_SOURCE_TABLE") or "").strip()
    if not source_table:
        raise AnesthesiaSyncConfigError(
            "ANESTHESIA_SQL_SOURCE_TABLE is not configured."
        )
    if not _SAFE_SOURCE_RE.fullmatch(source_table):
        raise AnesthesiaSyncConfigError(
            "ANESTHESIA_SQL_SOURCE_TABLE may only contain letters, numbers, "
            "underscores, dots, and square brackets."
        )
    return source_table


def _provider_type() -> str:
    """Return the provider type filter used by the MSSQL query."""
    return str(_config_value("ANESTHESIA_SQL_PROVIDER_TYPE") or "Anes Resident")


def _query_timeout() -> int:
    """Return the MSSQL connection timeout in seconds."""
    timeout = _config_value("ANESTHESIA_SQL_TIMEOUT")
    return int(timeout) if timeout is not None else 30


def _build_stop_time_query() -> str:
    """Build the default MSSQL query for the anesthesia stop-time source."""
    source_table = _source_table()
    return (
        "SELECT\n"
        "    ProviderID,\n"
        "    ProviderName,\n"
        f"    {_WORK_DATE_SQL} AS WorkDate,\n"
        "    MAX(ANESTHESIA_STOP_EVENTTIME) AS StopDateTime\n"
        f"FROM {source_table}\n"
        "WHERE ProviderType = ?\n"
        "  AND ANESTHESIA_STOP_EVENTTIME IS NOT NULL\n"
        f"  AND {_WORK_DATE_SQL} BETWEEN ? AND ?\n"
        "GROUP BY\n"
        "    ProviderID,\n"
        "    ProviderName,\n"
        f"    {_WORK_DATE_SQL}\n"
        "ORDER BY WorkDate ASC, ProviderName ASC"
    )


def _load_pyodbc() -> Any:
    """Import pyodbc only when the MSSQL sync is used."""
    try:
        return importlib.import_module("pyodbc")
    except ModuleNotFoundError as exc:
        raise AnesthesiaSyncDependencyError(
            "pyodbc is not installed. Run `uv sync --extra mssql` and make sure "
            "an ODBC SQL Server driver is available on this machine."
        ) from exc


def _row_to_mapping(columns: Sequence[str], row: Sequence[Any]) -> dict[str, Any]:
    """Convert a pyodbc result row into a named mapping."""
    return dict(zip(columns, row, strict=False))


def _coerce_date(value: Any, *, field_name: str) -> date:
    """Convert a row value into a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.split(" ", 1)[0])
        except ValueError as exc:
            raise AnesthesiaSyncError(
                f"Invalid {field_name} value returned by MSSQL: {value!r}"
            ) from exc
    raise AnesthesiaSyncError(
        f"Unsupported {field_name} type returned by MSSQL: {type(value).__name__}"
    )


def _coerce_datetime(value: Any, *, field_name: str) -> datetime:
    """Convert a row value into a datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace(" ", "T", 1))
        except ValueError as exc:
            raise AnesthesiaSyncError(
                f"Invalid {field_name} value returned by MSSQL: {value!r}"
            ) from exc
    raise AnesthesiaSyncError(
        f"Unsupported {field_name} type returned by MSSQL: {type(value).__name__}"
    )


def _record_from_row(row: Mapping[str, Any]) -> AnesthesiaStopRecord:
    """Build a normalized stop-time record from a SQL row."""
    provider_id_raw = row.get("ProviderID")
    provider_id = str(provider_id_raw).strip() if provider_id_raw is not None else None
    provider_name = str(row.get("ProviderName") or "").strip()
    return AnesthesiaStopRecord(
        provider_id=provider_id or None,
        provider_name=provider_name,
        work_date=_coerce_date(row.get("WorkDate"), field_name="WorkDate"),
        stop_datetime=_coerce_datetime(
            row.get("StopDateTime"), field_name="StopDateTime"
        ),
    )


def fetch_anesthesia_stop_records(
    start_date: date, end_date: date
) -> list[AnesthesiaStopRecord]:
    """Fetch grouped anesthesia stop times from the configured MSSQL source."""
    pyodbc = _load_pyodbc()
    try:
        connection = pyodbc.connect(_connection_string(), timeout=_query_timeout())
    except Exception as exc:
        raise AnesthesiaSyncError(
            "Failed to connect to the anesthesia MSSQL source."
        ) from exc

    try:
        cursor = connection.cursor()
        cursor.execute(_build_stop_time_query(), _provider_type(), start_date, end_date)
        columns = [str(column[0]) for column in cursor.description]
        return [
            _record_from_row(_row_to_mapping(columns, row)) for row in cursor.fetchall()
        ]
    except AnesthesiaSyncError:
        raise
    except Exception as exc:
        raise AnesthesiaSyncError("Failed to query anesthesia stop times.") from exc
    finally:
        connection.close()


def _normalize_identifier(raw_value: str | None) -> str | None:
    """Normalize a provider or resident identifier for matching."""
    if raw_value is None:
        return None
    normalized = str(raw_value).strip().casefold()
    return normalized or None


def _normalize_name(raw_name: str) -> str:
    """Normalize whitespace and case in a resident/provider name."""
    return " ".join(raw_name.split()).casefold()


def _name_keys(raw_name: str) -> set[str]:
    """Return match keys for a resident/provider name."""
    normalized = _normalize_name(raw_name)
    if not normalized:
        return set()

    keys = {normalized}
    if "," in normalized:
        last_name, remainder = (part.strip() for part in normalized.split(",", 1))
        first_tokens = remainder.split()
        if first_tokens:
            first_name = first_tokens[0]
            keys.add(f"{last_name}, {first_name}")
            keys.add(f"{first_name} {last_name}")
        return keys

    name_parts = normalized.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]
        keys.add(f"{first_name} {last_name}")
        keys.add(f"{last_name}, {first_name}")
    return keys


def _resident_name_keys(resident: Resident) -> set[str]:
    """Return all name-based match keys for a resident."""
    keys = _name_keys(resident.name)
    if resident.first_name and resident.last_name:
        keys.update(_name_keys(f"{resident.first_name} {resident.last_name}"))
        keys.update(_name_keys(f"{resident.last_name}, {resident.first_name}"))
    return keys


def _register_lookup(
    lookup: dict[str, Resident | object], key: str | None, resident: Resident
) -> None:
    """Register a resident lookup key and mark collisions as ambiguous."""
    if not key:
        return
    existing = lookup.get(key)
    if existing is None:
        lookup[key] = resident
        return
    if existing is resident or existing is _AMBIGUOUS:
        return
    lookup[key] = _AMBIGUOUS


def _build_resident_lookups() -> tuple[ResidentLookup, ResidentLookup]:
    """Build identifier and name lookups for resident matching."""
    by_identifier: ResidentLookup = {}
    by_name: ResidentLookup = {}

    for resident in Resident.query.all():
        _register_lookup(
            by_identifier,
            _normalize_identifier(resident.epic_id),
            resident,
        )
        for key in _resident_name_keys(resident):
            _register_lookup(by_name, key, resident)

    return by_identifier, by_name


def _build_entry_lookup(start_date: date, end_date: date) -> EntryLookup:
    """Load candidate time entries for the requested date range."""
    entries = (
        TimeEntry.query.filter(
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        )
        .options(joinedload(TimeEntry.role), joinedload(TimeEntry.resident))
        .all()
    )
    lookup: EntryLookup = defaultdict(list)
    for entry in entries:
        lookup[entry.resident_id, entry.date].append(entry)
    return lookup


def _stop_records_for_sync(
    start_date: date,
    end_date: date,
    *,
    records: Sequence[AnesthesiaStopRecord] | None,
) -> list[AnesthesiaStopRecord]:
    """Return provided stop records or fetch them from MSSQL."""
    if records is not None:
        return list(records)
    return fetch_anesthesia_stop_records(start_date, end_date)


def _match_resident(
    record: AnesthesiaStopRecord,
    *,
    by_identifier: Mapping[str, Resident | object],
    by_name: Mapping[str, Resident | object],
) -> tuple[Resident | None, str]:
    """Match an external record to a resident."""
    provider_key = _normalize_identifier(record.provider_id)
    if provider_key:
        identifier_match = by_identifier.get(provider_key)
        if identifier_match is _AMBIGUOUS:
            return None, "ambiguous"
        if isinstance(identifier_match, Resident):
            return identifier_match, "identifier"

    matched_residents: dict[int, Resident] = {}
    for key in _name_keys(record.provider_name):
        name_match = by_name.get(key)
        if name_match is _AMBIGUOUS:
            return None, "ambiguous"
        if isinstance(name_match, Resident):
            matched_residents[name_match.id] = name_match

    if len(matched_residents) == 1:
        return next(iter(matched_residents.values())), "name"
    if matched_residents:
        return None, "ambiguous"
    return None, "missing"


def _choose_target_entry(
    entries: Sequence[TimeEntry], *, overwrite_existing: bool
) -> TimeEntry | None:
    """Choose the best entry to receive a synced stop time."""
    non_call_team_entries = [
        entry for entry in entries if not (entry.role and entry.role.is_call_team)
    ]
    candidate_pools = [non_call_team_entries]
    if non_call_team_entries != list(entries):
        candidate_pools.append(list(entries))

    for pool in candidate_pools:
        if not pool:
            continue
        if len(pool) == 1:
            return pool[0]
        if not overwrite_existing:
            blank_stop_entries = [
                entry for entry in pool if entry.anesthesia_stop_time is None
            ]
            if len(blank_stop_entries) == 1:
                return blank_stop_entries[0]

    return None


def _format_time_value(value: time | None) -> str | None:
    """Format a time for audit payloads."""
    return value.strftime("%H:%M") if value else None


def _process_record(
    record: AnesthesiaStopRecord,
    *,
    context: _SyncContext,
    stats: _SyncStats,
    pending_updates: list[_PendingAuditUpdate],
) -> None:
    """Match one external record and apply it to a candidate time entry."""
    resident, match_status = _match_resident(
        record,
        by_identifier=context.by_identifier,
        by_name=context.by_name,
    )
    if resident is None:
        if match_status == "ambiguous":
            stats.skipped_ambiguous_resident += 1
        else:
            stats.skipped_missing_resident += 1
        return

    stats.matched_residents += 1
    candidate_entries = context.entries_by_key.get((resident.id, record.work_date))
    if not candidate_entries:
        stats.skipped_missing_entry += 1
        return

    target_entry = _choose_target_entry(
        candidate_entries,
        overwrite_existing=context.overwrite_existing,
    )
    if target_entry is None:
        stats.skipped_ambiguous_entry += 1
        return

    new_stop_time = record.stop_time
    if target_entry.anesthesia_stop_time == new_stop_time:
        stats.unchanged_entries += 1
        return
    if target_entry.anesthesia_stop_time is not None and not context.overwrite_existing:
        stats.skipped_existing_stop_time += 1
        return

    stats.planned_updates += 1
    if context.dry_run:
        return

    old_stop_time = target_entry.anesthesia_stop_time
    target_entry.anesthesia_stop_time = new_stop_time
    stats.applied_updates += 1
    pending_updates.append(
        _PendingAuditUpdate(
            entry=target_entry,
            old_stop_time=old_stop_time,
            record=record,
        )
    )


def _persist_updates(
    pending_updates: Sequence[_PendingAuditUpdate],
    *,
    result: AnesthesiaSyncResult,
    user: str | None,
) -> None:
    """Write audit logs and commit synced time-entry updates."""
    try:
        for pending_update in pending_updates:
            entry = pending_update.entry
            record = pending_update.record
            log_update_strict(
                "TimeEntry",
                entry.id,
                changes={
                    "anesthesia_stop_time": {
                        "old": _format_time_value(pending_update.old_stop_time),
                        "new": _format_time_value(entry.anesthesia_stop_time),
                    }
                },
                details={
                    "entry_id": entry.id,
                    "resident_id": entry.resident_id,
                    "resident": entry.resident.name if entry.resident else None,
                    "role": entry.role.name if entry.role else None,
                    "date": entry.date.isoformat(),
                    "provider_id": record.provider_id,
                    "provider_name": record.provider_name,
                    "source": "anesthesia_stop_sync",
                },
                user=user,
            )

        log_import_strict("anesthesia_stop_sync", result.summary(), user=user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def sync_anesthesia_stop_times(  # noqa: PLR0913
    start_date: date,
    end_date: date,
    *,
    overwrite_existing: bool = False,
    dry_run: bool = False,
    user: str | None = None,
    records: Sequence[AnesthesiaStopRecord] | None = None,
) -> AnesthesiaSyncResult:
    """Sync anesthesia stop times into matching anesthesia-stop fields."""
    if end_date < start_date:
        raise AnesthesiaSyncError("end_date must be on or after start_date.")

    stop_records = _stop_records_for_sync(
        start_date,
        end_date,
        records=records,
    )
    by_identifier, by_name = _build_resident_lookups()
    entries_by_key = _build_entry_lookup(start_date, end_date)
    context = _SyncContext(
        by_identifier=by_identifier,
        by_name=by_name,
        entries_by_key=entries_by_key,
        overwrite_existing=overwrite_existing,
        dry_run=dry_run,
    )
    stats = _SyncStats()
    pending_updates: list[_PendingAuditUpdate] = []

    for record in stop_records:
        _process_record(
            record,
            context=context,
            stats=stats,
            pending_updates=pending_updates,
        )

    result = stats.to_result(
        fetched_records=len(stop_records),
        dry_run=dry_run,
    )

    if dry_run:
        return result

    _persist_updates(pending_updates, result=result, user=user)
    logger.info(result.summary())
    return result
