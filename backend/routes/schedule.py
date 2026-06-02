"""Schedule import routes."""

import csv
import logging
from dataclasses import dataclass
from datetime import date
from io import StringIO
from logging import Logger

import requests
from flask import Blueprint, current_app
from sqlalchemy.exc import IntegrityError

from backend.audit import log_create_strict, log_import_strict, log_update_strict
from backend.auth import get_first_call_role_names, is_admin, is_first_call
from backend.holidays import is_weekend_or_holiday
from backend.instance_config import (
    CALL_TEAM_ROLE_NAMES,
    LATE_ROLE_NAMES,
    SCHEDULE_ROLE_NAMES,
    WEEKDAY_BACKUP_ROLE_NAMES,
)
from backend.models import DailySheet, Resident, Role, TimeEntry, db
from backend.payroll_audit import (
    filter_payroll_resident_changes,
    payroll_resident_details,
)
from backend.routes._helpers import (
    commit_flash_redirect,
    flash_sheet_redirect,
    parse_iso_date,
    rollback_flash_redirect,
)
from backend.type_defs import ScheduleImportResult, ScheduleResidentChanges

bp: Blueprint = Blueprint("schedule", __name__, url_prefix="/schedule")
logger: Logger = logging.getLogger(__name__)


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
    updated_changes: ScheduleResidentChanges | None = None
    skipped_unknown: bool = False
    skipped_conflict: bool = False


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
        return flash_sheet_redirect(
            date_str,
            "Only the first call resident or an admin can import schedules",
            "error",
        )

    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet and daily_sheet.locked:
        return flash_sheet_redirect(
            date_str,
            "Cannot import schedule - sheet is locked",
            "error",
        )

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


def _parse_schedule_rows(csv_text: str) -> list[ScheduleRow]:
    """Parse the relevant schedule CSV rows from an Amion response."""
    rows: list[ScheduleRow] = []
    for line in csv.reader(StringIO(csv_text)):
        if len(line) < 9 or line[0].startswith("Field"):
            continue

        raw_epic_id = line[1].strip('"').strip()
        rows.append(
            ScheduleRow(
                resident_name=line[0].strip('"').strip(),
                epic_id=(
                    raw_epic_id.removeprefix("EPICID:")
                    if raw_epic_id.startswith("EPICID:")
                    else None
                ),
                assignment_name=line[3].strip('"').strip(),
            )
        )
    return rows


def _load_schedule_rows(sheet_date: date) -> list[ScheduleRow]:
    """Fetch and parse schedule rows from Amion for a sheet date."""
    amion_url = _build_schedule_import_url(sheet_date)
    logger.info("Fetching schedule from Amion for date: %s", sheet_date)
    response = requests.get(amion_url, timeout=10)
    response.raise_for_status()
    logger.debug(
        "Parsed %d schedule rows from Amion",
        len(rows := _parse_schedule_rows(response.text)),
    )
    return rows


def _log_schedule_import(date_str: str, import_result: ScheduleImportResult) -> None:
    """Persist audit logs for a schedule import."""
    db.session.flush()

    for resident in import_result["created_residents"]:
        log_create_strict(
            "Resident",
            resident.id,
            payroll_resident_details(
                resident,
                date=date_str,
                source="schedule_import",
            ),
        )
    for resident, changes in import_result["updated_residents"]:
        if payroll_changes := filter_payroll_resident_changes(changes):
            log_update_strict(
                "Resident",
                resident.id,
                changes=payroll_changes,
                details=payroll_resident_details(
                    resident,
                    date=date_str,
                    source="schedule_import",
                ),
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


def _import_schedule_rows(
    rows: list[ScheduleRow],
    *,
    sheet_date: date,
    date_str: str,
) -> ScheduleImportResult:
    """Create schedule entries and audit logs for pre-fetched rows."""
    import_result = _process_entries(rows, sheet_date)
    _log_schedule_import(date_str, import_result)
    return import_result


@bp.route("/<date_str>/import", methods=["POST"])
def import_schedule(date_str):
    """Import schedule from Amion for a specific date."""
    try:
        sheet_date = parse_iso_date(date_str)
        denial_response = _validate_schedule_import_access(sheet_date, date_str)
        if denial_response is not None:
            return denial_response
        rows = _load_schedule_rows(sheet_date)

    except requests.RequestException:
        logger.exception("Error fetching data from Amion")
        return rollback_flash_redirect(
            "sheets.view",
            "Error fetching data from Amion.",
            date_str=date_str,
        )
    except Exception:
        logger.exception("Error importing schedule")
        return rollback_flash_redirect(
            "sheets.view",
            "Error importing schedule.",
            date_str=date_str,
        )

    return commit_flash_redirect(
        lambda: _import_schedule_rows(
            rows,
            sheet_date=sheet_date,
            date_str=date_str,
        ),
        endpoint="sheets.view",
        logger=logger,
        errors=("Error importing schedule", "Error importing schedule."),
        success_message=_build_schedule_import_flash,
        date_str=date_str,
    )


def _resident_keys(resident_name: str, epic_id: str | None) -> set[tuple[str, str]]:
    """Return normalized identifiers for matching a resident across rows."""
    keys: set[tuple[str, str]] = set()
    normalized_name = resident_name.casefold().strip()
    if normalized_name:
        keys.add(("name", normalized_name))
    if epic_id:
        keys.add(("epic_id", epic_id))
    return keys


def _schedule_role_names() -> frozenset[str]:
    """Return importable schedule role names, including the full call team."""
    return (
        SCHEDULE_ROLE_NAMES
        | CALL_TEAM_ROLE_NAMES
        | frozenset(get_first_call_role_names())
    )


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


def _resolve_schedule_resident(row: ScheduleRow) -> ResidentResolution:
    """Resolve a schedule row to an existing or newly-created resident."""
    resident = (
        Resident.query.filter_by(epic_id=row.epic_id).first() if row.epic_id else None
    )
    match_source = "epic_id" if resident is not None else None
    if resident is None:
        resident = Resident.query.filter_by(name=row.resident_name).first()
        if resident is not None:
            match_source = "name"

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
            resident = Resident(name=row.resident_name, active=True)
            db.session.add(resident)
            db.session.flush()
            logger.info(
                "Created resident during schedule import: %s (no EPIC ID)",
                row.resident_name,
            )
            return ResidentResolution(resident, created_resident=resident)

        logger.info(
            "Skipping schedule row for unknown resident: %s (EPIC ID: %s)",
            row.resident_name,
            row.epic_id,
        )
        return ResidentResolution(None, skipped_unknown=True)

    if not resident.epic_id and row.epic_id:
        resident.epic_id = row.epic_id
        logger.info(
            "Updated resident %s with EPIC ID: %s",
            row.resident_name,
            row.epic_id,
        )
        return ResidentResolution(
            resident,
            updated_changes={"epic_id": {"old": None, "new": row.epic_id}},
        )

    return ResidentResolution(resident)


def _process_entries(
    rows: list[ScheduleRow],
    sheet_date: date,
) -> ScheduleImportResult:
    """Process CSV lines and create time entries."""
    entries_created = 0
    created_residents: list[Resident] = []
    updated_residents: list[tuple[Resident, ScheduleResidentChanges]] = []
    created_entries: list[TimeEntry] = []
    skipped_weekday_backups = 0
    skipped_unknown_residents = 0
    skipped_conflicts = 0
    skip_weekday_backups = not is_weekend_or_holiday(sheet_date)
    late_assignment_keys = (
        {
            key
            for row in rows
            if row.assignment_name in LATE_ROLE_NAMES
            for key in _resident_keys(row.resident_name, row.epic_id)
        }
        if skip_weekday_backups
        else set()
    )
    schedule_role_names = _schedule_role_names()
    roles_by_name = {
        role.name: role
        for role in Role.query.filter(Role.name.in_(schedule_role_names)).all()
    }

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
        skipped_unknown_residents += resolution.skipped_unknown
        skipped_conflicts += resolution.skipped_conflict
        resident = resolution.resident
        if resident is None:
            continue

        if created_resident := resolution.created_resident:
            created_residents.append(created_resident)
        if updated_changes := resolution.updated_changes:
            updated_residents.append((resident, updated_changes))

        entries_created += _create_time_entry_if_missing(
            sheet_date,
            resident,
            role,
            created_entries,
        )

    return {
        "entries_created": entries_created,
        "created_residents": created_residents,
        "updated_residents": updated_residents,
        "created_entries": created_entries,
        "skipped_unknown_residents": skipped_unknown_residents,
        "skipped_conflicts": skipped_conflicts,
        "skipped_weekday_backups": skipped_weekday_backups,
    }
