"""
Staff list import from Amion API.

Fetches and parses the staff list (Report 706) from Amion to populate
resident information including class year, email, phone, and other details.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Sequence
from typing import Any

import requests
from email_validator import EmailNotValidError, validate_email
from flask import current_app, has_app_context

from backend.audit import log_create, log_import, log_update
from backend.config import Config
from backend.errors import ValidationError
from backend.models import Resident, db
from backend.type_defs import ImportResult, StaffList, StaffRecord

logger = logging.getLogger(__name__)

CLASS_YEAR_MAP: dict[str, str] = {
    "CA1": "CA-1",
    "CA2": "CA-2",
    "CA3": "CA-3",
    "Fellow": "Fellow",
    "OMFS": "OMFS",
}


def _clean_cell(value: str | None) -> str:
    return value.strip() if value else ""


def _epic_id_from_row(row: dict[str, str | None]) -> str | None:
    """Return the EPIC ID from a parsed row, if present."""
    unique_id = _clean_cell(row.get("Unique ID"))
    if not unique_id.startswith("EPICID:"):
        return None
    epic_id = unique_id.removeprefix("EPICID:")
    return epic_id or None


def _normalized_email(raw_email: str, *, name: str) -> str | None:
    """Return a normalized email, or None when blank/invalid."""
    if not raw_email:
        return None

    try:
        return validate_email(raw_email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        logger.warning(
            "Invalid email %r for %r discarded during staff import",
            raw_email,
            name,
        )
        return None


def _phone_from_row(row: dict[str, str | None]) -> str | None:
    """Return the preferred phone number from a parsed row, or None."""
    return _clean_cell(row.get("Pager")) or _clean_cell(row.get("Tel.")) or None


def _split_name(name: str) -> tuple[str | None, str | None]:
    """Split a full name into first/last components."""
    parts = name.rsplit(" ", 1)
    first_name = parts[0].strip() if parts else None
    last_name = parts[1].strip() if len(parts) > 1 else None
    return first_name, last_name


def _get_amion_base_url() -> str:
    """Return the Amion base URL from the active Flask config."""
    if has_app_context():
        base_url = current_app.config.get("AMION_BASE_URL", Config.AMION_BASE_URL)
    else:
        base_url = Config.AMION_BASE_URL
    return str(base_url or "").strip()


def fetch_staff_list(schedule_code: str) -> str:
    """
    Fetch staff list from Amion API.

    Args:
        schedule_code: The Amion schedule code (e.g., "upennane")

    Returns:
        CSV content as string

    Raises:
        requests.RequestException: If the API request fails
    """
    url = f"{_get_amion_base_url()}?Lo={schedule_code}&Rpt=706"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.text


def parse_staff_list(csv_content: str) -> StaffList:
    """
    Parse staff list CSV content.

    Expected format (tab-delimited):
    Staff type | Name | Unique ID  | Backup ID | Abbreviation | Staff type unique ID |
    Pager | Tel. | Email

    Args:
        csv_content: CSV content as string

    Returns:
        List of dictionaries with staff information
    """
    staff_list: StaffList = []

    # Split content into lines and find the header
    lines = csv_content.strip().split("\n")

    header_index: int | None = None
    for i, line in enumerate(lines):
        if "Staff type" in line and "Name" in line:
            header_index = i
            break

    if header_index is None:
        raise ValidationError("Could not find header line in staff list")

    # Parse CSV starting from header
    lines_subset = [line for idx, line in enumerate(lines) if idx >= header_index]
    csv_reader = csv.DictReader(lines_subset, delimiter="\t", skipinitialspace=True)

    for row in csv_reader:
        # Skip empty rows or placeholders
        name = _clean_cell(row.get("Name"))
        if not name:
            continue

        # Skip placeholder entries
        if "placeholder" in name.lower():
            continue

        epic_id = _epic_id_from_row(row)
        if not epic_id:
            logger.warning(
                "Skipping row during staff import: missing EPIC ID. Name: %r",
                name,
            )
            continue
        raw_email = _clean_cell(row.get("Email"))
        staff_list.append(
            StaffRecord(
                name=name,
                epic_id=epic_id,
                class_year=_clean_cell(row.get("Staff type")),
                backup_id=_clean_cell(row.get("Backup ID")),
                abbreviation=_clean_cell(row.get("Abbreviation")),
                phone=_phone_from_row(row),
                email=_normalized_email(raw_email, name=name),
            )
        )

    return staff_list


def _update_resident_fields(
    resident: Resident,
    staff: StaffRecord,
    normalized_class_year: str,
    first_name: str | None,
    last_name: str | None,
) -> dict[str, dict[str, Any]]:
    """Apply staff record fields to an existing resident; return change map."""
    changes: dict[str, dict[str, Any]] = {}
    for attr, new_val in [
        ("class_year", normalized_class_year),
        ("email", staff["email"]),
        ("phone", staff["phone"]),
        ("abbreviation", staff["abbreviation"]),
        ("backup_id", staff["backup_id"]),
        ("name", staff["name"]),
    ]:
        if attr == "email" and new_val is None:
            continue
        if attr == "phone" and new_val is None:
            continue
        old_val = getattr(resident, attr)
        if old_val != new_val:
            changes[attr] = {"old": old_val, "new": new_val}
            setattr(resident, attr, new_val)

    if resident.first_name != first_name or resident.last_name != last_name:
        changes["first_name"] = {"old": resident.first_name, "new": first_name}
        changes["last_name"] = {"old": resident.last_name, "new": last_name}
        resident.first_name = first_name
        resident.last_name = last_name

    return changes


def import_staff_to_database(
    staff_list: Sequence[StaffRecord], user: str | None = None
) -> tuple[int, int, int]:
    """
    Import staff list into database.

    Creates new residents or updates existing ones with staff information.

    Args:
        staff_list: List of staff dictionaries from parse_staff_list()
        user: Username for audit logging

    Returns:
        Tuple of (created_count, updated_count, skipped_count)
    """
    created = 0
    updated = 0
    skipped = 0

    # Track residents to audit-log after commit (id is not yet available for new ones)
    created_residents: list[Resident] = []
    updated_residents: list[tuple[Resident, dict[str, Any]]] = []

    for staff in staff_list:
        epic_id = staff["epic_id"]
        normalized_class_year = CLASS_YEAR_MAP.get(
            staff["class_year"], staff["class_year"]
        )

        first_name, last_name = _split_name(staff["name"])

        resident = Resident.get_by_epic_id(epic_id)

        if resident:
            changes = _update_resident_fields(
                resident, staff, normalized_class_year or "", first_name, last_name
            )
            if changes:
                updated += 1
                updated_residents.append((resident, changes))
            else:
                skipped += 1
        else:
            # Create new resident
            resident = Resident(
                name=staff["name"],
                first_name=first_name,
                last_name=last_name,
                epic_id=epic_id,
                class_year=normalized_class_year,
                email=staff["email"],
                phone=staff["phone"],
                abbreviation=staff["abbreviation"],
                backup_id=staff["backup_id"],
                active=True,
            )
            db.session.add(resident)
            created_residents.append(resident)
            created += 1

    # Commit all changes
    db.session.commit()

    # Log per-resident audit events after commit so IDs are assigned
    for resident in created_residents:
        log_create(
            "Resident",
            resident.id,
            {
                "name": resident.name,
                "epic_id": resident.epic_id,
                "source": "staff_import",
            },
        )
    for resident, changes in updated_residents:
        log_update("Resident", resident.id, changes=changes)

    # Log the overall import
    log_import(
        "staff_list",
        f"Created: {created}, Updated: {updated}, Skipped: {skipped}",
        user=user,
    )

    return created, updated, skipped


def import_staff_list(schedule_code: str, user: str | None = None) -> ImportResult:
    """
    Complete staff list import workflow.

    Fetches staff list from Amion, parses it, and imports into database.

    Args:
        schedule_code: The Amion schedule code (e.g., "upennane")
        user: Username for audit logging

    Returns:
        Dictionary with import results:
        {
            'success': bool,
            'created': int,
            'updated': int,
            'skipped': int,
            'total_records': int,
            'error': str (if success=False)
        }
    """
    try:
        # Fetch from API
        csv_content = fetch_staff_list(schedule_code)

        # Parse CSV
        staff_list = parse_staff_list(csv_content)

        if not staff_list:
            return ImportResult(
                success=False,
                error="No staff records found in import",
                created=0,
                updated=0,
                skipped=0,
                total_records=0,
            )

        # Import to database
        created, updated, skipped = import_staff_to_database(staff_list, user)

        return ImportResult(
            success=True,
            created=created,
            updated=updated,
            skipped=skipped,
            total_records=len(staff_list),
            error=None,
        )

    except requests.RequestException:
        logger.exception("Failed to fetch staff list from Amion")
        return ImportResult(
            success=False,
            error="Failed to fetch staff list from Amion.",
            created=0,
            updated=0,
            skipped=0,
            total_records=0,
        )
    except Exception:
        db.session.rollback()
        logger.exception("Staff import failed")
        return ImportResult(
            success=False,
            error="Staff import failed.",
            created=0,
            updated=0,
            skipped=0,
            total_records=0,
        )
