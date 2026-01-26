"""
Staff list import from Amion API.

Fetches and parses the staff list (Report 706) from Amion to populate
resident information including class year, email, phone, and other details.
"""

import csv

import requests

from backend.audit import log_import
from backend.models import Resident, db


def fetch_staff_list(schedule_code: str = "upennane") -> str:
    """
    Fetch staff list from Amion API.

    Args:
        schedule_code: The Amion schedule code (default: upennane)

    Returns:
        CSV content as string

    Raises:
        requests.RequestException: If the API request fails
    """
    url = f"http://www.amion.com/cgi-bin/ocs?Lo={schedule_code}&Rpt=706"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.text


def parse_staff_list(csv_content: str) -> list[dict[str, str]]:
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
    staff_list = []

    # Split content into lines and find the header
    lines = csv_content.strip().split("\n")

    # Find the header line (contains "Staff type")
    header_index = None
    for i, line in enumerate(lines):
        if "Staff type" in line and "Name" in line:
            header_index = i
            break

    if header_index is None:
        raise ValueError("Could not find header line in staff list")

    # Parse CSV starting from header
    csv_reader = csv.DictReader(
        lines[header_index:], delimiter="\t", skipinitialspace=True
    )

    for row in csv_reader:
        # Skip empty rows or placeholders
        if not row.get("Name") or not row["Name"].strip():
            continue

        # Skip placeholder entries
        if "placeholder" in row["Name"].lower():
            continue

        # Extract EPIC ID from "Unique ID" field (format: "EPICID:R######")
        unique_id = row.get("Unique ID", "")
        epic_id = None
        if unique_id.startswith("EPICID:"):
            epic_id = unique_id.replace("EPICID:", "")

        # Only include staff with valid EPIC IDs
        if epic_id:
            staff_list.append(
                {
                    "name": row["Name"].strip(),
                    "epic_id": epic_id,
                    "class_year": row.get("Staff type", "").strip(),
                    "backup_id": row.get("Backup ID", "").strip(),
                    "abbreviation": row.get("Abbreviation", "").strip(),
                    "phone": row.get("Pager", "").strip()
                    or row.get("Tel.", "").strip(),
                    "email": row.get("Email", "").strip(),
                }
            )

    return staff_list


def import_staff_to_database(
    staff_list: list[dict[str, str]], user: str | None = None
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

    for staff in staff_list:
        epic_id = staff["epic_id"]

        # Find existing resident by EPIC ID
        resident = Resident.get_by_epic_id(epic_id)

        if resident:
            # Update existing resident
            changed = False

            if resident.class_year != staff["class_year"]:
                resident.class_year = staff["class_year"]
                changed = True

            if resident.email != staff["email"]:
                resident.email = staff["email"]
                changed = True

            if resident.phone != staff["phone"]:
                resident.phone = staff["phone"]
                changed = True

            if resident.abbreviation != staff["abbreviation"]:
                resident.abbreviation = staff["abbreviation"]
                changed = True

            if resident.backup_id != staff["backup_id"]:
                resident.backup_id = staff["backup_id"]
                changed = True

            # Update name if it's different (might be more formal in staff list)
            if resident.name != staff["name"]:
                resident.name = staff["name"]
                changed = True

            if changed:
                updated += 1
            else:
                skipped += 1
        else:
            # Create new resident
            resident = Resident(
                name=staff["name"],
                epic_id=epic_id,
                class_year=staff["class_year"],
                email=staff["email"],
                phone=staff["phone"],
                abbreviation=staff["abbreviation"],
                backup_id=staff["backup_id"],
                active=True,
            )
            db.session.add(resident)
            created += 1

    # Commit all changes
    db.session.commit()

    # Log the import
    log_import(
        "staff_list",
        f"Created: {created}, Updated: {updated}, Skipped: {skipped}",
        user=user,
    )

    return created, updated, skipped


def import_staff_list(
    schedule_code: str = "upennane", user: str | None = None
) -> dict[str, any]:
    """
    Complete staff list import workflow.

    Fetches staff list from Amion, parses it, and imports into database.

    Args:
        schedule_code: The Amion schedule code (default: upennane)
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
            return {
                "success": False,
                "error": "No staff records found in import",
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "total_records": 0,
            }

        # Import to database
        created, updated, skipped = import_staff_to_database(staff_list, user)

        return {
            "success": True,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "total_records": len(staff_list),
            "error": None,
        }

    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"Failed to fetch staff list from Amion: {e!s}",
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "total_records": 0,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Import failed: {e!s}",
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "total_records": 0,
        }
