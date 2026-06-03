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
from email_validator import EmailNotValidError
from flask import current_app, has_app_context

from backend.audit import log_create, log_import, log_update
from backend.config import Config
from backend.errors import ValidationError
from backend.imports.staff_fields import staff_fields
from backend.models import Resident, db
from backend.reporting.payroll import (
    filter_payroll_resident_changes,
    payroll_resident_details,
)
from backend.type_defs import ImportResult, StaffList, StaffRecord
from backend.utils import normalize_email

logger = logging.getLogger(__name__)


def _staff_import_result(
    *,
    success: bool,
    error: str | None,
    counts: tuple[int, int, int] = (0, 0, 0),
    total_records: int = 0,
) -> ImportResult:
    """Build a normalized staff-import result payload."""
    created, updated, skipped = counts
    return ImportResult(
        success=success,
        error=error,
        created=created,
        updated=updated,
        skipped=skipped,
        total_records=total_records,
    )


def _epic_id_from_row(row: dict[str, str | None]) -> str | None:
    """Return the EPIC ID from a parsed row, if present."""
    unique_id = staff_fields.clean_text(row.get("Unique ID"))
    if not unique_id.startswith("EPICID:"):
        return None
    epic_id = unique_id.removeprefix("EPICID:")
    return epic_id or None


def _normalized_email(raw_email: str, *, name: str) -> str | None:
    """Return a normalized email, or None when blank/invalid."""
    try:
        return normalize_email(raw_email)
    except EmailNotValidError:
        logger.warning(
            "Invalid email %r for %r discarded during staff import",
            raw_email,
            name,
        )
        return None


def _phone_from_row(row: dict[str, str | None]) -> str | None:
    """Return the preferred phone number from a parsed row, or None."""
    return (
        staff_fields.clean_text(row.get("Pager"))
        or staff_fields.clean_text(row.get("Tel."))
        or None
    )


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
        name = staff_fields.clean_text(row.get("Name"))
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
        raw_email = staff_fields.clean_text(row.get("Email"))
        staff_list.append(
            StaffRecord(
                name=name,
                epic_id=epic_id,
                class_year=staff_fields.clean_text(row.get("Staff type")),
                backup_id=staff_fields.clean_text(row.get("Backup ID")),
                abbreviation=staff_fields.clean_text(row.get("Abbreviation")),
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


def _persist_staff_import_audit(
    created_residents: Sequence[Resident],
    updated_residents: Sequence[tuple[Resident, dict[str, Any]]],
    *,
    summary: str,
    user: str | None,
) -> None:
    """Persist best-effort audit rows after resident changes are committed."""
    try:
        for resident in created_residents:
            log_create(
                "Resident",
                resident.id,
                payroll_resident_details(resident, source="staff_import"),
            )
        for resident, changes in updated_residents:
            if payroll_changes := filter_payroll_resident_changes(changes):
                log_update("Resident", resident.id, changes=payroll_changes)
        log_import(
            "staff_list",
            summary,
            user=user,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Staff import audit persistence failed")


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
        normalized_class_year = staff_fields.class_year(staff["class_year"]) or ""

        first_name, last_name = staff_fields.split_name(staff["name"])

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

    summary = f"Created: {created}, Updated: {updated}, Skipped: {skipped}"
    _persist_staff_import_audit(
        created_residents,
        updated_residents,
        summary=summary,
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
            return _staff_import_result(
                success=False,
                error="No staff records found in import",
            )

        # Import to database
        created, updated, skipped = import_staff_to_database(staff_list, user)

        return _staff_import_result(
            success=True,
            error=None,
            counts=(created, updated, skipped),
            total_records=len(staff_list),
        )

    except requests.RequestException:
        logger.exception("Failed to fetch staff list from Amion")
        return _staff_import_result(
            success=False,
            error="Failed to fetch staff list from Amion.",
        )
    except Exception:
        db.session.rollback()
        logger.exception("Staff import failed")
        return _staff_import_result(
            success=False,
            error="Staff import failed.",
        )
