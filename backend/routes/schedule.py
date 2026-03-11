"""Schedule import routes."""

import csv
import logging
from dataclasses import dataclass
from datetime import date
from io import StringIO
from logging import Logger

import requests
from flask import Blueprint, current_app, flash, redirect, url_for
from sqlalchemy.exc import IntegrityError

from ..audit import log_create_strict, log_import_strict, log_update_strict
from ..auth import get_first_call_role_names, is_admin, is_first_call
from ..holidays import is_weekend_or_holiday
from ..models import DailySheet, Resident, Role, TimeEntry, db
from ..type_defs import ScheduleImportResult

bp: Blueprint = Blueprint("schedule", __name__, url_prefix="/schedule")
logger: Logger = logging.getLogger(__name__)

LATE_ROLE_NAMES = frozenset({"Late Late 1", "Late Late 2"})
WEEKDAY_BACKUP_ROLE_NAMES = frozenset({"Backup"})
SCHEDULE_ROLE_NAMES = frozenset(
    {
        "First Call",
        "Second Call",
        "Third Call",
        "OB Flex",
        "Cardiac Call",
        "ECC 1",
        "ECC 2",
        "ECC 3",
        "ECC 4",
        "ECC 5",
        "ECA 1",
        "ECA 2",
        "Late Late 1",
        "Late Late 2",
        "PPMC",
        "Held",
        "EP/HUP 13",
        "H12",
        "H13",
        "H14",
        "HUP EP 12",
        "Backup",
        "Cardiac Backup",
    }
)


@dataclass(frozen=True, slots=True)
class ScheduleRow:
    """Normalized data for one imported Amion schedule row."""

    resident_name: str
    epic_id: str | None
    assignment_name: str


@dataclass(frozen=True, slots=True)
class ResidentResolution:
    """Outcome of resolving a schedule row to a resident."""

    resident: Resident | None
    created_resident: Resident | None = None
    updated_changes: dict[str, dict[str, str | None]] | None = None
    skipped_unknown: bool = False
    skipped_conflict: bool = False


def _sheet_view_redirect(date_str: str):
    """Return the sheet view redirect for a given date."""
    return redirect(url_for("sheets.view", date_str=date_str))


def _validate_schedule_import_access(sheet_date: date, date_str: str):
    """Return a redirect response when schedule import is not allowed."""
    first_call_is_known = (
        TimeEntry.query.join(Role)
        .filter(
            TimeEntry.date == sheet_date,
            Role.name.in_(get_first_call_role_names()),
        )
        .first()
        is not None
    )
    if first_call_is_known and not (is_admin() or is_first_call(sheet_date)):
        flash("Only the first call resident or an admin can import schedules", "error")
        return _sheet_view_redirect(date_str)

    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot import schedule - sheet is locked", "error")
        return _sheet_view_redirect(date_str)

    return None


def _build_schedule_import_url(sheet_date: date) -> str:
    """Build the Amion schedule import URL for a sheet date."""
    schedule_code = current_app.config.get("AMION_SCHEDULE_CODE", "upennane")
    amion_base_url = current_app.config.get(
        "AMION_BASE_URL", "https://www.amion.com/cgi-bin/ocs"
    ).strip()
    return (
        f"{amion_base_url}?Lo={schedule_code}&Rpt=619&Day={sheet_date.day}"
        f"&Month={sheet_date.month}"
    )


def _is_schedule_data_line(line: list[str]) -> bool:
    """Return True when a CSV row contains imported schedule data."""
    return len(line) >= 9 and not line[0].startswith("Field")


def _normalize_epic_id(raw: str) -> str | None:
    """Extract an EPIC ID from a raw schedule cell."""
    if raw.startswith("EPICID:"):
        return raw.removeprefix("EPICID:")
    return None


def _parse_schedule_row(line: list[str]) -> ScheduleRow:
    """Return the normalized fields used from an imported schedule row."""
    return ScheduleRow(
        resident_name=line[0].strip('"').strip(),
        epic_id=_normalize_epic_id(line[1].strip('"').strip()),
        assignment_name=line[3].strip('"').strip(),
    )


def _parse_schedule_rows(csv_text: str) -> list[ScheduleRow]:
    """Parse the relevant schedule CSV rows from an Amion response."""
    csv_reader = csv.reader(StringIO(csv_text))
    return [
        _parse_schedule_row(line) for line in csv_reader if _is_schedule_data_line(line)
    ]


def _load_schedule_rows(sheet_date: date) -> list[ScheduleRow]:
    """Fetch and parse schedule rows from Amion for a sheet date."""
    amion_url = _build_schedule_import_url(sheet_date)
    logger.info("Fetching schedule from Amion for date: %s", sheet_date)
    response = requests.get(amion_url, timeout=10)
    response.raise_for_status()
    rows = _parse_schedule_rows(response.text)
    logger.debug("Parsed %d schedule rows from Amion", len(rows))
    return rows


def _schedule_import_error(message: str) -> None:
    """Rollback and flash a schedule import error."""
    db.session.rollback()
    flash(message, "error")


def _log_schedule_import(date_str: str, import_result: ScheduleImportResult) -> None:
    """Persist audit logs for a schedule import."""
    db.session.flush()

    for resident in import_result["created_residents"]:
        log_create_strict(
            "Resident",
            resident.id,
            {
                "name": resident.name,
                "epic_id": resident.epic_id,
                "date": date_str,
                "source": "schedule_import",
            },
        )
    for resident, changes in import_result["updated_residents"]:
        log_update_strict(
            "Resident",
            resident.id,
            changes=changes,
            details={
                "name": resident.name,
                "date": date_str,
                "source": "schedule_import",
            },
        )
    for entry in import_result["created_entries"]:
        log_create_strict(
            "TimeEntry",
            entry.id,
            {
                "date": date_str,
                "resident_id": entry.resident_id,
                "resident": (
                    entry.resident.name if entry.resident else entry.resident_id
                ),
                "role": entry.role.name if entry.role else entry.role_id,
                "source": "schedule_import",
            },
        )

    log_import_strict(
        "Schedule",
        (
            f"Date: {date_str}, "
            f"Entries created: {import_result['entries_created']}, "
            f"Residents created: {len(import_result['created_residents'])}, "
            f"Residents updated: {len(import_result['updated_residents'])}, "
            f"Unknown residents skipped: {import_result['skipped_unknown_residents']}, "
            f"Resident conflicts skipped: {import_result['skipped_conflicts']}, "
            f"Weekday backups skipped: {import_result['skipped_weekday_backups']}"
        ),
    )


def _build_schedule_import_flash(
    import_result: ScheduleImportResult,
) -> tuple[str, str]:
    """Return the user-facing flash message for an import result."""
    if import_result["entries_created"] > 0:
        message = (
            "Successfully imported "
            f"{import_result['entries_created']} schedule entries from Amion"
        )
        skipped_details: list[str] = []
        if import_result["skipped_unknown_residents"] > 0:
            skipped_details.append(
                f"{import_result['skipped_unknown_residents']} rows skipped "
                "for unknown residents"
            )
        if import_result["skipped_conflicts"] > 0:
            skipped_details.append(
                f"{import_result['skipped_conflicts']} rows skipped "
                "for resident/EPIC conflicts"
            )
        if skipped_details:
            message += f" ({', '.join(skipped_details)})"
        return message, "success"

    if (
        import_result["skipped_unknown_residents"] > 0
        or import_result["skipped_conflicts"] > 0
        or import_result["skipped_weekday_backups"] > 0
    ):
        skipped_messages: list[str] = []
        if import_result["skipped_unknown_residents"] > 0:
            skipped_messages.append(
                f"{import_result['skipped_unknown_residents']} rows were skipped "
                "because the resident was not found."
            )
        if import_result["skipped_conflicts"] > 0:
            skipped_messages.append(
                f"{import_result['skipped_conflicts']} rows were skipped "
                "because the resident name matched a different EPIC ID."
            )
        if import_result["skipped_weekday_backups"] > 0:
            skipped_messages.append(
                f"{import_result['skipped_weekday_backups']} rows were skipped "
                "by weekday-backup rules because the resident also had a "
                "Late assignment."
            )
        return f"No new entries imported. {' '.join(skipped_messages)}", "info"

    return "No new entries to import (entries may already exist)", "info"


@bp.route("/<date_str>/import", methods=["POST"])
def import_schedule(date_str):
    """Import schedule from Amion for a specific date."""
    try:
        sheet_date = date.fromisoformat(date_str)
        denial_response = _validate_schedule_import_access(sheet_date, date_str)
        if denial_response is not None:
            return denial_response

        import_result = _process_entries(_load_schedule_rows(sheet_date), sheet_date)
        _log_schedule_import(date_str, import_result)
        db.session.commit()

        message, category = _build_schedule_import_flash(import_result)
        flash(message, category)

    except requests.RequestException:
        logger.exception("Error fetching data from Amion")
        _schedule_import_error("Error fetching data from Amion.")
    except Exception:
        logger.exception("Error importing schedule")
        _schedule_import_error("Error importing schedule.")

    return _sheet_view_redirect(date_str)


def _resident_keys(resident_name: str, epic_id: str | None) -> set[tuple[str, str]]:
    """Return normalized identifiers for matching a resident across rows."""
    keys: set[tuple[str, str]] = set()
    normalized_name = resident_name.casefold().strip()
    if normalized_name:
        keys.add(("name", normalized_name))
    if epic_id:
        keys.add(("epic_id", epic_id))
    return keys


def _collect_late_assignment_keys(rows: list[ScheduleRow]) -> set[tuple[str, str]]:
    """Return resident identifiers assigned to late roles in the import."""
    late_assignment_keys: set[tuple[str, str]] = set()
    for row in rows:
        if row.assignment_name in LATE_ROLE_NAMES:
            late_assignment_keys.update(_resident_keys(row.resident_name, row.epic_id))
    return late_assignment_keys


def _schedule_role_names() -> frozenset[str]:
    """Return importable schedule role names, including configured aliases."""
    return SCHEDULE_ROLE_NAMES.union(get_first_call_role_names())


def _load_schedule_roles() -> dict[str, Role]:
    """Return the configured importable roles keyed by name."""
    roles = Role.query.filter(Role.name.in_(_schedule_role_names())).all()
    return {role.name: role for role in roles}


def _create_time_entry_if_missing(
    sheet_date: date,
    resident: Resident,
    role: Role,
    created_entries: list[TimeEntry],
) -> bool:
    """Create a time entry when one does not already exist."""
    existing_entry = TimeEntry.query.filter_by(
        date=sheet_date, resident_id=resident.id, role_id=role.id
    ).first()
    if existing_entry:
        return False

    entry = TimeEntry(
        date=sheet_date,
        resident_id=resident.id,
        role_id=role.id,
        exit_time=None,
    )
    try:
        with db.session.begin_nested():
            db.session.add(entry)
            db.session.flush()
    except IntegrityError:
        with db.session.no_autoflush:
            duplicate_entry = TimeEntry.query.filter_by(
                date=sheet_date,
                resident_id=resident.id,
                role_id=role.id,
            ).first()
        if duplicate_entry:
            logger.info(
                "Skipped duplicate time entry for resident %s, role %s on %s",
                resident.id,
                role.id,
                sheet_date,
            )
            return False
        raise

    created_entries.append(entry)
    return True


def _should_skip_weekday_backup(
    row: ScheduleRow,
    *,
    skip_weekday_backups: bool,
    late_assignment_keys: set[tuple[str, str]],
    sheet_date: date,
) -> bool:
    """Return True when weekday backup rules suppress a schedule row."""
    if not skip_weekday_backups or row.assignment_name not in WEEKDAY_BACKUP_ROLE_NAMES:
        return False

    if not late_assignment_keys.intersection(
        _resident_keys(row.resident_name, row.epic_id)
    ):
        return False

    logger.info(
        (
            "Skipping weekday %s import for %s on %s because "
            "the resident is also assigned to a Late role"
        ),
        row.assignment_name,
        row.resident_name,
        sheet_date,
    )
    return True


def _find_matching_resident(
    row: ScheduleRow,
) -> tuple[Resident | None, str | None]:
    """Find a resident by EPIC ID first, then by name."""
    if row.epic_id:
        resident = Resident.query.filter_by(epic_id=row.epic_id).first()
        if resident is not None:
            return resident, "epic_id"

    resident = Resident.query.filter_by(name=row.resident_name).first()
    if resident is not None:
        return resident, "name"

    return None, None


def _create_name_only_resident(row: ScheduleRow) -> Resident:
    """Create a resident for a row that only provides a name."""
    resident = Resident(name=row.resident_name, active=True)
    db.session.add(resident)
    db.session.flush()
    logger.info(
        "Created resident during schedule import: %s (no EPIC ID)",
        row.resident_name,
    )
    return resident


def _resident_epic_id_update(
    resident: Resident, row: ScheduleRow
) -> dict[str, dict[str, str | None]] | None:
    """Return EPIC-ID changes applied while resolving a resident."""
    if resident.epic_id or not row.epic_id:
        return None

    resident.epic_id = row.epic_id
    logger.info("Updated resident %s with EPIC ID: %s", row.resident_name, row.epic_id)
    return {"epic_id": {"old": None, "new": row.epic_id}}


def _resolve_schedule_resident(row: ScheduleRow) -> ResidentResolution:
    """Resolve a schedule row to an existing or newly-created resident."""
    resident, match_source = _find_matching_resident(row)
    if (
        resident is not None
        and match_source == "name"
        and row.epic_id
        and resident.epic_id
        and resident.epic_id != row.epic_id
    ):
        logger.info(
            (
                "Skipping schedule row for resident name/EPIC "
                "conflict: %s (row EPIC ID: %s, existing resident "
                "EPIC ID: %s)"
            ),
            row.resident_name,
            row.epic_id,
            resident.epic_id,
        )
        return ResidentResolution(None, skipped_conflict=True)

    if resident is None:
        if row.resident_name and not row.epic_id:
            resident = _create_name_only_resident(row)
            return ResidentResolution(resident, created_resident=resident)

        logger.info(
            "Skipping schedule row for unknown resident: %s (EPIC ID: %s)",
            row.resident_name,
            row.epic_id,
        )
        return ResidentResolution(None, skipped_unknown=True)

    return ResidentResolution(
        resident,
        updated_changes=_resident_epic_id_update(resident, row),
    )


def _process_entries(
    rows: list[ScheduleRow],
    sheet_date: date,
) -> ScheduleImportResult:
    """Process CSV lines and create time entries."""
    entries_created = 0
    created_residents: list[Resident] = []
    updated_residents: list[tuple[Resident, dict[str, dict[str, str | None]]]] = []
    created_entries: list[TimeEntry] = []
    skipped_weekday_backups = 0
    skipped_unknown_residents = 0
    skipped_conflicts = 0
    skip_weekday_backups = not is_weekend_or_holiday(sheet_date)
    late_assignment_keys = (
        _collect_late_assignment_keys(rows) if skip_weekday_backups else set()
    )
    roles_by_name = _load_schedule_roles()
    schedule_role_names = _schedule_role_names()

    for row in rows:
        if row.assignment_name not in schedule_role_names:
            continue

        if _should_skip_weekday_backup(
            row,
            skip_weekday_backups=skip_weekday_backups,
            late_assignment_keys=late_assignment_keys,
            sheet_date=sheet_date,
        ):
            skipped_weekday_backups += 1
            continue

        role = roles_by_name.get(row.assignment_name)
        if not role:
            logger.warning("Role not found: %s", row.assignment_name)
            continue

        resolution = _resolve_schedule_resident(row)
        if resolution.skipped_unknown:
            skipped_unknown_residents += 1
        if resolution.skipped_conflict:
            skipped_conflicts += 1
        resident = resolution.resident
        if resident is None:
            continue

        if resolution.created_resident is not None:
            created_residents.append(resolution.created_resident)
        if resolution.updated_changes is not None:
            updated_residents.append((resident, resolution.updated_changes))

        if _create_time_entry_if_missing(sheet_date, resident, role, created_entries):
            entries_created += 1

    return {
        "entries_created": entries_created,
        "created_residents": created_residents,
        "updated_residents": updated_residents,
        "created_entries": created_entries,
        "skipped_unknown_residents": skipped_unknown_residents,
        "skipped_conflicts": skipped_conflicts,
        "skipped_weekday_backups": skipped_weekday_backups,
    }
