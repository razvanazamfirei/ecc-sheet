"""Shared utilities for report generation."""

import csv
from datetime import date
from io import StringIO

from .models import Resident, TimeEntry, db


def build_entries_query(
    start_date: date, end_date: date, resident_id: str | int | None
):
    """Build query for entries within date range, filtered by resident."""
    query = TimeEntry.query.filter(
        TimeEntry.date >= start_date, TimeEntry.date <= end_date
    )
    if resident_id:
        query = query.filter(TimeEntry.resident_id == resident_id)
    return query


def get_resident_name(resident_id: str | int | None) -> str | None:
    """Look up resident name by ID."""
    if not resident_id:
        return None
    resident = db.session.get(Resident, resident_id)
    return resident.name if resident else None


def aggregate_entries_by_resident(entries) -> dict:
    """
    Aggregate time entries by resident.

    Returns:
        Dictionary mapping resident names to their entries and total overtime.
        Example: {"John Doe": {"entries": [...], "total_overtime": 2.5}}
    """
    resident_data = {}
    for entry in entries:
        res_name = entry.resident.name
        if res_name not in resident_data:
            resident_data[res_name] = {"entries": [], "total_overtime": 0.0}

        overtime = entry.calculate_overtime_hours()
        resident_data[res_name]["entries"].append(
            {
                "date": entry.date.strftime("%Y-%m-%d"),
                "role": entry.role.name,
                "exit_time": entry.exit_time.strftime("%H:%M")
                if entry.exit_time
                else "",
                "overtime": overtime,
            }
        )
        resident_data[res_name]["total_overtime"] += overtime

    return resident_data


def generate_csv_content(entries) -> str:
    """Generate CSV content from time entries."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Resident", "Role", "Exit Time", "Overtime Hours"])

    for entry in entries:
        writer.writerow(
            [
                entry.date.strftime("%Y-%m-%d"),
                entry.resident.name,
                entry.role.name,
                entry.exit_time.strftime("%H:%M") if entry.exit_time else "",
                f"{entry.calculate_overtime_hours():.2f}",
            ]
        )

    return output.getvalue()
