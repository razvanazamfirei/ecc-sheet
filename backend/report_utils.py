"""Shared utilities for report generation."""

import csv
from datetime import date
from io import BytesIO, StringIO

import openpyxl

from .models import Resident, Role, TimeEntry, db


def build_entries_query(
    start_date: date, end_date: date, resident_id: str | int | None
):
    """Build query for entries within date range, filtered by resident.

    Call team roles (is_call_team=True) are excluded from overtime reports.
    """
    query = TimeEntry.query.join(Role).filter(
        TimeEntry.date >= start_date,
        TimeEntry.date <= end_date,
        Role.is_call_team.isnot(True),
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
        Dictionary mapping resident_id (int) to their entries and total overtime.
        Example: {42: {"name": "John Doe", "entries": [...], "total_overtime": 2.5}}
    """
    resident_data = {}
    for entry in entries:
        res_id = entry.resident_id
        if res_id not in resident_data:
            resident_data[res_id] = {
                "name": entry.resident.name,
                "entries": [],
                "total_overtime": 0.0,
            }

        overtime = entry.overtime_hours
        resident_data[res_id]["entries"].append(
            {
                "date": entry.date.strftime("%Y-%m-%d"),
                "role": entry.role.name,
                "exit_time": entry.exit_time.strftime("%H:%M")
                if entry.exit_time
                else "",
                "overtime": overtime,
            }
        )
        resident_data[res_id]["total_overtime"] += overtime

    return resident_data


def generate_csv_content(entries) -> str:
    """Generate detailed CSV content from time entries."""
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
                f"{entry.overtime_hours:.2f}",
            ]
        )

    return output.getvalue()


def generate_billing_csv_content(resident_data: dict) -> str:
    """
    Generate billing/payroll CSV content from aggregated resident data.

    Args:
        resident_data: Dictionary from aggregate_entries_by_resident()

    Returns:
        CSV content with just Resident Name and Total Overtime Hours
    """
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Resident Name", "Total Overtime Hours"])

    # Sort by resident name for consistent output
    for data in sorted(resident_data.values(), key=lambda d: d["name"]):
        writer.writerow([data["name"], f"{data['total_overtime']:.2f}"])

    # Add grand total row
    grand_total = sum(data["total_overtime"] for data in resident_data.values())
    writer.writerow(["Grand Total", f"{grand_total:.2f}"])

    return output.getvalue()


def generate_payroll_xlsx(
    resident_data: dict, start_date: date, end_date: date, settings
) -> bytes:
    """
    Generate a Lawson/UPHS payroll export spreadsheet.

    Column layout (1-indexed):
      A=Program, B=HireDate, C=Employee, D=Company, E=Batch,
      F=LawsonID, G=filter(empty), H=PayCode, I=Hours,
      J-M=filter1-4(empty), N=Transdate, O=Dept, P=Expense,
      Q=AcctUnit, R-AA=empty, AB=note ("{MON} {label_suffix}")

    Only residents with a lawson_id are included.

    Args:
        resident_data: Dict from aggregate_entries_by_resident() keyed by name.
        start_date: Report start date (used for col AB month abbreviation).
        end_date: Report end date (used as Transdate in col N).
        settings: PayrollSettings instance.

    Returns:
        Bytes of the .xlsx workbook.
    """
    wb = openpyxl.Workbook()
    ws = wb.active

    # Header row
    headers = [
        "Program",  # A
        "",  # B (hire date — no header label per spec)
        "Employee",  # C
        "UPHS",  # D
        "Batch",  # E
        "Lawson ID #",  # F
        "filter",  # G
        "Pay Code",  # H
        "Hours",  # I
        "filter 1",  # J
        "filter 2",  # K
        "filter 3",  # L
        "filter 4",  # M
        "Transdate",  # N
        "Dept",  # O
        "Expense",  # P
        "Acct Unit",  # Q
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",  # R-AA (10 empty cols)
        "",  # AB note (header empty)
    ]
    ws.append(headers)

    month_abbrev = start_date.strftime('%b').upper()
    if settings.label_suffix:
        note = f"{month_abbrev} {settings.label_suffix}"
    else:
        note = month_abbrev

    for resident_id, data in sorted(
        resident_data.items(), key=lambda item: item[1]["name"]
    ):
        resident = db.session.get(Resident, resident_id)
        if resident is None or not resident.lawson_id:
            continue

        total_overtime = data["total_overtime"]
        hire_date_val = resident.hire_date

        # Build a 28-element row (cols A through AB)
        row = [None] * 28
        row[0] = settings.program  # A
        row[1] = hire_date_val  # B
        row[2] = data["name"]  # C
        row[3] = settings.company  # D
        row[4] = settings.batch  # E
        row[5] = resident.lawson_id  # F
        row[6] = None  # G (empty)
        row[7] = settings.pay_code  # H
        row[8] = round(total_overtime, 2)  # I
        # J-M (indices 9-12) remain None
        row[13] = end_date  # N
        row[14] = settings.dept  # O
        row[15] = settings.expense  # P
        row[16] = settings.acct_unit  # Q
        # R-AA (indices 17-26) remain None
        row[27] = note  # AB

        ws.append(row)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
