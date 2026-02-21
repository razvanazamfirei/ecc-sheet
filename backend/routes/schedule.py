"""Schedule import routes."""

import csv
import logging
from datetime import date, datetime
from io import StringIO

import requests
from flask import Blueprint, current_app, flash, redirect, url_for

from ..audit import log_import
from ..models import DailySheet, Resident, Role, TimeEntry, db

bp = Blueprint("schedule", __name__, url_prefix="/schedule")
logger = logging.getLogger(__name__)


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

        entries_created = _process_entries(data_lines, role_mapping, sheet_date)

        db.session.commit()

        # Log the import
        log_import(
            "Schedule",
            f"Date: {date_str}, Entries created: {entries_created}",
        )

        if entries_created > 0:
            flash(
                f"Successfully imported {entries_created} schedule entries from Amion",
                "success",
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


def _process_entries(
    data_lines: list[list[str]],
    role_mapping: dict[str, str],
    sheet_date: date,
) -> int:
    """Process CSV lines and create time entries."""
    entries_created = 0

    for line in data_lines:
        resident_name = line[0].strip('"')
        epic_id_raw = line[1].strip('"')
        assignment_name = line[3].strip('"')

        # Extract EPIC ID (e.g., "EPICID:R103348" -> "R103348")
        epic_id = None
        if epic_id_raw.startswith("EPICID:"):
            epic_id = epic_id_raw.replace("EPICID:", "")

        # Check if this is a role we care about
        if assignment_name in role_mapping:
            # Find or create resident by EPIC ID first, then by name
            resident = None
            if epic_id:
                resident = Resident.query.filter_by(epic_id=epic_id).first()

            if not resident:
                resident = Resident.query.filter_by(name=resident_name).first()

            if not resident:
                resident = Resident(name=resident_name, epic_id=epic_id, active=True)
                db.session.add(resident)
                db.session.flush()  # Get the ID
                logger.info(
                    "Created new resident: %s (EPIC ID: %s)", resident_name, epic_id
                )
            elif not resident.epic_id and epic_id:
                # Update existing resident with EPIC ID if missing
                resident.epic_id = epic_id
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
                entries_created += 1

    return entries_created
