"""Schedule import routes."""

import csv
import logging
from datetime import date, datetime
from io import StringIO
from logging import Logger

import requests
from flask import Blueprint, current_app, flash, redirect, url_for

from ..audit import log_create_strict, log_import_strict, log_update_strict
from ..holidays import is_weekend_or_holiday
from ..models import DailySheet, Resident, Role, TimeEntry, db

from ..type_defs import ScheduleImportResult
bp: Blueprint = Blueprint("schedule", __name__, url_prefix="/schedule")
logger: Logger = logging.getLogger(__name__)

LATE_ROLE_NAMES = frozenset({"Late Late 1", "Late Late 2"})
WEEKDAY_BACKUP_ROLE_NAMES = frozenset({"Backup"})


@bp.route("/<date_str>/import", methods=["POST"])
def import_schedule(date_str):
    """Import schedule from Amion for a specific date."""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if daily_sheet and daily_sheet.locked:
            flash("Cannot import schedule - sheet is locked", "error")
            return redirect(url_for("sheets.view", date_str=date_str))

        # Get schedule code from config
        schedule_code = current_app.config.get("AMION_SCHEDULE_CODE", "upennane")

        # Construct Amion URL
        day = sheet_date.day
        month = sheet_date.month
        amion_url = f"http://www.amion.com/cgi-bin/ocs?Lo={schedule_code}&Rpt=619&Day={day}&Month={month}"

        # Fetch data from Amion
        logger.info("Fetching schedule from Amion: %s", amion_url)
        response = requests.get(amion_url, timeout=10)
        response.raise_for_status()

        # Parse CSV data
        csv_data = StringIO(response.text)
        csv_reader = csv.reader(csv_data)

        # Skip header lines
        lines = list(csv_reader)
        data_lines = [
            line for line in lines if len(line) >= 9 and not line[0].startswith("Field")
        ]

        logger.debug("Parsed %d schedule rows from Amion", len(data_lines))

        # Relevant role names to import
        role_mapping = {
            "First Call": "First Call",
            "Second Call": "Second Call",
            "Third Call": "Third Call",
            "OB Flex": "OB Flex",
            "Cardiac Call": "Cardiac Call",
            "ECC 1": "ECC 1",
            "ECC 2": "ECC 2",
            "ECC 3": "ECC 3",
            "ECC 4": "ECC 4",
            "ECC 5": "ECC 5",
            "ECA 1": "ECA 1",
            "ECA 2": "ECA 2",
            "Late Late 1": "Late Late 1",
            "Late Late 2": "Late Late 2",
            "PPMC": "PPMC",
            "Held": "Held",
            "EP/HUP 13": "EP/HUP 13",
            "H12": "H12",
            "H13": "H13",
            "H14": "H14",
            "HUP EP 12": "HUP EP 12",
            "Backup": "Backup",
            "Cardiac Backup": "Cardiac Backup",
        }

        import_result = _process_entries(data_lines, role_mapping, sheet_date)
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

        # Log the import
        log_import_strict(
            "Schedule",
            (
                f"Date: {date_str}, "
                f"Entries created: {import_result['entries_created']}, "
                f"Residents created: {len(import_result['created_residents'])}, "
                f"Residents updated: {len(import_result['updated_residents'])}, "
                f"Unknown residents skipped: "
                f"{import_result['skipped_unknown_residents']}, "
                f"Weekday backups skipped: {import_result['skipped_weekday_backups']}"
            ),
        )
        db.session.commit()

        if import_result["entries_created"] > 0:
            message = (
                "Successfully imported "
                f"{import_result['entries_created']} schedule entries from Amion"
            )
            if import_result["skipped_unknown_residents"] > 0:
                message += (
                    f" ({import_result['skipped_unknown_residents']} rows skipped "
                    "for unknown residents)"
                )
            flash(
                message,
                "success",
            )
        elif (
            import_result["skipped_unknown_residents"] > 0
            or import_result["skipped_weekday_backups"] > 0
        ):
            skipped_messages: list[str] = []
            if import_result["skipped_unknown_residents"] > 0:
                skipped_messages.append(
                    f"{import_result['skipped_unknown_residents']} rows were skipped "
                    "because the resident was not found."
                )
            if import_result["skipped_weekday_backups"] > 0:
                skipped_messages.append(
                    f"{import_result['skipped_weekday_backups']} rows were skipped "
                    "by weekday-backup rules because the resident also had a "
                    "Late assignment."
                )
            flash(
                f"No new entries imported. {' '.join(skipped_messages)}",
                "info",
            )
        else:
            flash("No new entries to import (entries may already exist)", "info")

    except requests.RequestException as e:
        db.session.rollback()
        flash(f"Error fetching data from Amion: {e!s}", "error")
        logger.error("Amion fetch error: %s", e)
    except Exception as e:
        db.session.rollback()
        flash(f"Error importing schedule: {e!s}", "error")
        logger.error("Import error: %s", e)

    return redirect(url_for("sheets.view", date_str=date_str))


def _normalize_epic_id(raw: str) -> str | None:
    """Extract an EPIC ID from a raw schedule cell."""
    if raw.startswith("EPICID:"):
        return raw.removeprefix("EPICID:")
    return None


def _resident_keys(resident_name: str, epic_id: str | None) -> set[tuple[str, str]]:
    """Return normalized identifiers for matching a resident across rows."""
    keys: set[tuple[str, str]] = set()
    normalized_name = resident_name.casefold().strip()
    if normalized_name:
        keys.add(("name", normalized_name))
    if epic_id:
        keys.add(("epic_id", epic_id))
    return keys


def _collect_late_assignment_keys(data_lines: list[list[str]]) -> set[tuple[str, str]]:
    """Return resident identifiers assigned to late roles in the import."""
    late_assignment_keys: set[tuple[str, str]] = set()
    for line in data_lines:
        resident_name = line[0].strip('"').strip()
        epic_id = _normalize_epic_id(line[1].strip('"').strip())
        assignment_name = line[3].strip('"').strip()
        if assignment_name in LATE_ROLE_NAMES:
            late_assignment_keys.update(_resident_keys(resident_name, epic_id))
    return late_assignment_keys


def _process_entries(
    data_lines: list[list[str]],
    role_mapping: dict[str, str],
    sheet_date: date,
) -> ScheduleImportResult:
    """Process CSV lines and create time entries."""
    entries_created = 0
    created_residents: list[Resident] = []
    updated_residents: list[tuple[Resident, dict[str, dict[str, str | None]]]] = []
    created_entries: list[TimeEntry] = []
    skipped_weekday_backups = 0
    skipped_unknown_residents = 0
    skip_weekday_backups = not is_weekend_or_holiday(sheet_date)
    late_assignment_keys = (
        _collect_late_assignment_keys(data_lines) if skip_weekday_backups else set()
    )

    for line in data_lines:
        resident_name = line[0].strip('"').strip()
        epic_id = _normalize_epic_id(line[1].strip('"').strip())
        assignment_name = line[3].strip('"').strip()

        # Check if this is a role we care about
        if assignment_name in role_mapping:
            if (
                skip_weekday_backups
                and assignment_name in WEEKDAY_BACKUP_ROLE_NAMES
                and late_assignment_keys.intersection(
                    _resident_keys(resident_name, epic_id)
                )
            ):
                skipped_weekday_backups += 1
                logger.info(
                    (
                        "Skipping weekday %s import for %s on %s because "
                        "the resident is also assigned to a Late role"
                    ),
                    assignment_name,
                    resident_name,
                    sheet_date,
                )
                continue

            # Find resident by EPIC ID first, then by name.
            resident = None
            if epic_id:
                resident = Resident.query.filter_by(epic_id=epic_id).first()

            if not resident:
                resident = Resident.query.filter_by(name=resident_name).first()
                if (
                    resident
                    and epic_id
                    and resident.epic_id
                    and resident.epic_id != epic_id
                ):
                    skipped_unknown_residents += 1
                    logger.info(
                        (
                            "Skipping schedule row for resident name/EPIC "
                            "conflict: %s (row EPIC ID: %s, existing resident "
                            "EPIC ID: %s)"
                        ),
                        resident_name,
                        epic_id,
                        resident.epic_id,
                    )
                    continue

            if not resident:
                if resident_name and not epic_id:
                    resident = Resident(name=resident_name, active=True)
                    db.session.add(resident)
                    db.session.flush()
                    created_residents.append(resident)
                    logger.info(
                        "Created resident during schedule import: %s (no EPIC ID)",
                        resident_name,
                    )
                else:
                    skipped_unknown_residents += 1
                    logger.info(
                        "Skipping schedule row for unknown resident: %s (EPIC ID: %s)",
                        resident_name,
                        epic_id,
                    )
                    continue
            if not resident.epic_id and epic_id:
                # Update existing resident with EPIC ID if missing
                resident.epic_id = epic_id
                updated_residents.append(
                    (resident, {"epic_id": {"old": None, "new": epic_id}})
                )
                logger.info(
                    "Updated resident %s with EPIC ID: %s", resident_name, epic_id
                )

            # Find role
            role = Role.query.filter_by(name=role_mapping[assignment_name]).first()
            if not role:
                logger.warning("Role not found: %s", assignment_name)
                continue

            # Check if entry already exists for this resident/roles/date
            existing_entry = TimeEntry.query.filter_by(
                date=sheet_date, resident_id=resident.id, role_id=role.id
            ).first()

            if not existing_entry:
                # Create time entry without exit time (to be filled in later)
                entry = TimeEntry(
                    date=sheet_date,
                    resident_id=resident.id,
                    role_id=role.id,
                    exit_time=None,
                )
                db.session.add(entry)
                created_entries.append(entry)
                entries_created += 1

    return {
        "entries_created": entries_created,
        "created_residents": created_residents,
        "updated_residents": updated_residents,
        "created_entries": created_entries,
        "skipped_unknown_residents": skipped_unknown_residents,
        "skipped_weekday_backups": skipped_weekday_backups,
    }
