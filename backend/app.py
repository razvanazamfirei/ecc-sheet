import csv
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path

import requests
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from .audit import log_create, log_delete, log_import, log_lock, log_update
from .auth import admin_required, get_current_user, is_admin
from .config import Config
from .email_service import send_report_email
from .models import AuditLog, DailySheet, Resident, Role, TimeEntry, db
from .staff_import import import_staff_list
from .utils import get_philadelphia_time, philly_today, setup_logging

# Get the project root directory (parent of backend/)
project_root = Path(__file__).parent.parent

app = Flask(
    __name__,
    template_folder=str(project_root / "frontend" / "templates"),
    static_folder=str(project_root / "frontend" / "static"),
)
app.config.from_object(Config)
db.init_app(app)

# Initialize Flask-Migrate for database migrations
migrate = Migrate(app, db)

# Enable CSRF protection
csrf = CSRFProtect(app)

# Setup logging
logger = setup_logging()


# Make auth functions available in templates
@app.context_processor
def inject_auth():
    """Inject authentication functions into template context"""
    return {"current_user": get_current_user(), "is_admin": is_admin()}


def init_db():
    """Initialize database with default roles"""
    with app.app_context():
        db.create_all()

        # Create default roles if they don't exist
        default_roles = [
            ("ECA 1", 1),
            ("ECA 2", 2),
            ("ECC 1", 3),
            ("ECC 2", 4),
            ("ECC 3", 5),
            ("ECC 4", 6),
            ("ECC 5", 7),
            ("PPMC", 8),
            ("Late Late 1", 9),
            ("Late Late 2", 10),
            ("Held", 11),
            ("EP/HUP 13", 12),
            ("H12", 13),
            ("H13", 14),
            ("H14", 15),
            ("HUP EP 12", 16),
        ]

        for role_name, order in default_roles:
            if not Role.query.filter_by(name=role_name).first():
                cutoff_hour = app.config["ROLE_CUTOFF_HOURS"].get(
                    role_name, app.config["DEFAULT_CUTOFF_HOUR"]
                )
                cutoff_minute = app.config["ROLE_CUTOFF_MINUTES"].get(
                    role_name, app.config["DEFAULT_CUTOFF_MINUTE"]
                )
                role = Role(
                    name=role_name,
                    cutoff_hour=cutoff_hour,
                    cutoff_minute=cutoff_minute,
                    display_order=order,
                )
                db.session.add(role)

        db.session.commit()


@app.route("/")
def index():
    """Dashboard showing today's sheet"""
    today = philly_today()
    daily_sheet = DailySheet.query.filter_by(date=today).first()

    if not daily_sheet:
        daily_sheet = DailySheet(date=today)
        db.session.add(daily_sheet)
        db.session.commit()

    # Get all time entries for today
    time_entries = TimeEntry.query.filter_by(date=today).order_by(TimeEntry.id).all()

    # Get all roles ordered
    roles = Role.query.order_by(Role.display_order).all()

    # Calculate previous and next dates
    prev_date = today - timedelta(days=1)
    next_date = today + timedelta(days=1)

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        time_entries=time_entries,
        roles=roles,
        today=today,
        prev_date=prev_date,
        next_date=next_date,
        current_time=get_philadelphia_time(),
    )


@app.route("/sheet/<date_str>")
def view_sheet(date_str):
    """View sheet for a specific date"""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
    except ValueError:
        flash("Invalid date format", "error")
        return redirect(url_for("index"))

    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()

    if not daily_sheet:
        daily_sheet = DailySheet(date=sheet_date)
        db.session.add(daily_sheet)
        db.session.commit()

    time_entries = (
        TimeEntry.query.filter_by(date=sheet_date).order_by(TimeEntry.id).all()
    )
    roles = Role.query.order_by(Role.display_order).all()

    # Calculate previous and next dates
    prev_date = sheet_date - timedelta(days=1)
    next_date = sheet_date + timedelta(days=1)

    return render_template(
        "index.html",
        daily_sheet=daily_sheet,
        time_entries=time_entries,
        roles=roles,
        today=sheet_date,
        prev_date=prev_date,
        next_date=next_date,
        current_time=get_philadelphia_time(),
    )


@app.route("/add_entry", methods=["POST"])
def add_entry():
    """Add a new time entry"""
    sheet_date_str = ""
    try:
        sheet_date_str = request.form.get("date")
        sheet_date = datetime.strptime(sheet_date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if daily_sheet and daily_sheet.locked:
            flash("Cannot add entry - sheet is locked", "error")
            return redirect(url_for("view_sheet", date_str=sheet_date_str))

        resident_id = request.form.get("resident_id")
        role_id = request.form.get("role_id")
        exit_time_str = request.form.get("exit_time")

        # Parse exit time
        exit_time = None
        if exit_time_str:
            exit_time = datetime.strptime(exit_time_str, "%H:%M").time()  # noqa: DTZ007

        # Parse boolean fields (checkboxes send "on" when checked)
        airway_assist = request.form.get("airway_assist") == "on"
        emergency = request.form.get("emergency") == "on"
        dinner_break = request.form.get("dinner_break") == "on"
        paper_record = request.form.get("paper_record") == "on"

        entry = TimeEntry(
            date=sheet_date,
            resident_id=resident_id,
            role_id=role_id,
            exit_time=exit_time,
            airway_assist=airway_assist,
            emergency=emergency,
            dinner_break=dinner_break,
            paper_record=paper_record,
        )

        db.session.add(entry)
        db.session.commit()

        # Log the action
        log_create(
            "TimeEntry",
            entry.id,
            {
                "date": sheet_date_str,
                "resident": entry.resident.name,
                "role": entry.role.name,
            },
        )

        flash("Entry added successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding entry: {e!s}", "error")

    return redirect(url_for("view_sheet", date_str=sheet_date_str))


@app.route("/update_entry/<int:entry_id>", methods=["POST"])
def update_entry(entry_id):
    """Update an existing time entry"""
    entry = TimeEntry.query.get_or_404(entry_id)

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=entry.date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot update entry - sheet is locked", "error")
        return redirect(url_for("view_sheet", date_str=entry.date.strftime("%Y-%m-%d")))

    try:
        exit_time_str = request.form.get("exit_time")
        if exit_time_str:
            entry.exit_time = datetime.strptime(exit_time_str, "%H:%M").time()  # noqa: DTZ007
        else:
            entry.exit_time = None

        db.session.commit()

        # Log the action
        log_update(
            "TimeEntry",
            entry.id,
            {"exit_time": exit_time_str or "cleared"},
        )

        flash("Entry updated successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating entry: {e!s}", "error")

    return redirect(url_for("view_sheet", date_str=entry.date.strftime("%Y-%m-%d")))


@app.route("/delete_entry/<int:entry_id>", methods=["POST"])
def delete_entry(entry_id):
    """Delete a time entry"""
    entry = TimeEntry.query.get_or_404(entry_id)
    sheet_date = entry.date

    # Check if sheet is locked
    daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
    if daily_sheet and daily_sheet.locked:
        flash("Cannot delete entry - sheet is locked", "error")
        return redirect(url_for("view_sheet", date_str=sheet_date.strftime("%Y-%m-%d")))

    try:
        # Log before deleting
        log_delete(
            "TimeEntry",
            entry.id,
            {
                "date": str(entry.date),
                "resident": entry.resident.name,
                "role": entry.role.name,
            },
        )

        db.session.delete(entry)
        db.session.commit()
        flash("Entry deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting entry: {e!s}", "error")

    return redirect(url_for("view_sheet", date_str=sheet_date.strftime("%Y-%m-%d")))


@app.route("/lock_sheet/<date_str>", methods=["POST"])
def lock_sheet(date_str):
    """Lock/unlock a daily sheet"""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()

        if not daily_sheet:
            daily_sheet = DailySheet(date=sheet_date)
            db.session.add(daily_sheet)

        daily_sheet.locked = not daily_sheet.locked

        # Track who and when
        if daily_sheet.locked:
            daily_sheet.locked_by = app.config["USER_NAME"]
            daily_sheet.locked_at = datetime.now()  # noqa: DTZ005
        else:
            daily_sheet.locked_by = None
            daily_sheet.locked_at = None

        db.session.commit()

        # Log lock/unlock action
        log_lock(date_str, daily_sheet.locked)

        status = "locked" if daily_sheet.locked else "unlocked"
        flash(f"Sheet {status} successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error locking sheet: {e!s}", "error")

    return redirect(url_for("view_sheet", date_str=date_str))


@app.route("/import_schedule/<date_str>", methods=["POST"])
def import_schedule(date_str):
    """Import schedule from Amion for a specific date"""
    try:
        sheet_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=sheet_date).first()
        if daily_sheet and daily_sheet.locked:
            flash("Cannot import schedule - sheet is locked", "error")
            return redirect(url_for("view_sheet", date_str=date_str))

        # Construct Amion URL
        day = sheet_date.day
        month = sheet_date.month
        amion_url = f"http://www.amion.com/cgi-bin/ocs?Lo=upennane&Rpt=619&Day={day}&Month={month}"

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

        # Relevant role names to import
        role_mapping = {
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
        }

        entries_created = 0

        entries_created = process_entries(
            data_lines, entries_created, role_mapping, sheet_date
        )

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

    return redirect(url_for("view_sheet", date_str=date_str))


def process_entries(
    data_lines: list[list[str]],
    entries_created: int,
    role_mapping: dict[str, str],
    sheet_date: date,
) -> int:
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

            # Check if entry already exists for this resident/role/date
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
                    airway_assist=False,
                    emergency=False,
                    dinner_break=False,
                    paper_record=False,
                )
                db.session.add(entry)
                entries_created += 1
    return entries_created


@app.route("/residents")
@admin_required
def residents():
    """Manage residents"""
    all_residents = Resident.query.order_by(Resident.name).all()
    return render_template("residents.html", residents=all_residents)


@app.route("/add_resident", methods=["POST"])
def add_resident():
    """Add a new resident"""
    name = request.form.get("name", "").strip()

    if not name:
        flash("Resident name is required", "error")
        return redirect(url_for("residents"))

    try:
        resident = Resident(name=name)
        db.session.add(resident)
        db.session.commit()
        flash(f"Resident {name} added successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding resident: {e!s}", "error")

    return redirect(url_for("residents"))


@app.route("/toggle_resident/<int:resident_id>", methods=["POST"])
def toggle_resident(resident_id):
    """Toggle resident active status"""
    resident = Resident.query.get_or_404(resident_id)

    try:
        resident.active = not resident.active
        db.session.commit()
        status = "activated" if resident.active else "deactivated"
        flash(f"Resident {resident.name} {status}", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating resident: {e!s}", "error")

    return redirect(url_for("residents"))


@app.route("/import_staff_list", methods=["POST"])
@admin_required
def import_staff_list_route():
    """Import staff list from Amion to populate resident information"""

    try:
        result = import_staff_list(user=get_current_user())

        if result["success"]:
            flash(
                f"Staff list imported successfully: "
                f"{result['created']} created, "
                f"{result['updated']} updated, "
                f"{result['skipped']} skipped",
                "success",
            )
        else:
            flash(f"Import failed: {result['error']}", "error")

    except Exception as e:
        flash(f"Error importing staff list: {e!s}", "error")

    return redirect(url_for("residents"))


@app.route("/roles")
@admin_required
def roles():
    """Manage roles"""
    all_roles = Role.query.order_by(Role.display_order).all()
    return render_template("roles.html", roles=all_roles)


@app.route("/update_role/<int:role_id>", methods=["POST"])
def update_role(role_id):
    """Update role cutoff time"""
    role = Role.query.get_or_404(role_id)

    try:
        cutoff_hour = int(request.form.get("cutoff_hour", 17))
        cutoff_minute = int(request.form.get("cutoff_minute", 30))

        # Validate ranges
        if not (0 <= cutoff_hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        if not (0 <= cutoff_minute <= 59):
            raise ValueError("Minute must be between 0 and 59")

        role.cutoff_hour = cutoff_hour
        role.cutoff_minute = cutoff_minute
        db.session.commit()
        flash(f"Role {role.name} updated successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error updating role: {e!s}", "error")

    return redirect(url_for("roles"))


@app.route("/reports")
def reports():
    """View reports page"""
    return render_template("reports.html")


@app.route("/api/report", methods=["POST"])
def generate_report():
    """Generate report for date range"""
    try:
        start_date = datetime.strptime(  # noqa: DTZ007
            request.form.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()  # noqa: DTZ007
        resident_id = request.form.get("resident_id")

        # Build query for time entries
        query = TimeEntry.query.filter(
            TimeEntry.date >= start_date, TimeEntry.date <= end_date
        )

        # Filter by resident if specified
        resident_name = None
        if resident_id:
            query = query.filter(TimeEntry.resident_id == resident_id)
            resident = Resident.query.get(resident_id)
            if resident:
                resident_name = resident.name

        entries = query.all()

        # Aggregate by resident
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

        return render_template(
            "report_results.html",
            start_date=start_date,
            end_date=end_date,
            resident_data=resident_data,
            resident_name=resident_name,
            resident_id=resident_id,
        )

    except Exception as e:
        flash(f"Error generating report: {e!s}", "error")
        return redirect(url_for("reports"))


@app.route("/api/report/export_csv", methods=["POST"])
def export_report_csv():
    """Export report to CSV"""
    try:
        start_date = datetime.strptime(  # noqa: DTZ007
            request.form.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()  # noqa: DTZ007
        resident_id = request.form.get("resident_id")

        # Build query for time entries
        query = TimeEntry.query.filter(
            TimeEntry.date >= start_date, TimeEntry.date <= end_date
        )

        # Filter by resident if specified
        if resident_id:
            query = query.filter(TimeEntry.resident_id == resident_id)

        entries = query.order_by(TimeEntry.date, TimeEntry.resident_id).all()

        # Generate CSV
        output = StringIO()
        csv_writer = csv.writer(output)

        # Write header
        csv_writer.writerow(["Date", "Resident", "Role", "Exit Time", "Overtime Hours"])

        # Write data rows
        for entry in entries:
            csv_writer.writerow(
                [
                    entry.date.strftime("%Y-%m-%d"),
                    entry.resident.name,
                    entry.role.name,
                    entry.exit_time.strftime("%H:%M") if entry.exit_time else "",
                    f"{entry.calculate_overtime_hours():.2f}",
                ]
            )

        # Create response
        output.seek(0)

        filename = f"overtime_report_{start_date}_{end_date}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        flash(f"Error exporting report: {e!s}", "error")
        return redirect(url_for("reports"))


@app.route("/api/report/send_email", methods=["POST"])
def send_report_email_route():
    """Send report via email"""
    try:
        start_date = datetime.strptime(  # noqa: DTZ007
            request.form.get("start_date"), "%Y-%m-%d"
        ).date()
        end_date = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date()  # noqa: DTZ007
        resident_id = request.form.get("resident_id")
        recipient_email = request.form.get("recipient_email")

        # Get resident name if specified
        resident_name = None
        if resident_id:
            resident = Resident.query.get(resident_id)
            if resident:
                resident_name = resident.name

        # Send email
        success = send_report_email(
            start_date=start_date,
            end_date=end_date,
            recipient_email=recipient_email,
            resident_id=int(resident_id) if resident_id else None,
            resident_name=resident_name,
        )

        if success:
            flash(f"Report emailed successfully to {recipient_email or 'configured recipient'}", "success")
        else:
            flash("Failed to send email. Check email configuration and logs.", "error")

    except Exception as e:
        flash(f"Error sending email: {e!s}", "error")
        logger.error("Error in send_report_email_route: %s", e)

    return redirect(url_for("reports"))


@app.route("/api/residents/active")
def get_active_residents():
    """API endpoint to get active residents"""
    residents = Resident.query.filter_by(active=True).order_by(Resident.name).all()
    return jsonify([{"id": r.id, "name": r.name} for r in residents])


@app.route("/api/roles")
def get_roles():
    """API endpoint to get all roles"""
    all_roles = Role.query.order_by(Role.display_order).all()
    return jsonify(
        [{"id": r.id, "name": r.name, "cutoff_hour": r.cutoff_hour} for r in all_roles]
    )


@app.route("/audit")
@admin_required
def audit_log():
    """View audit trail"""
    # Get filter parameters
    limit = request.args.get("limit", 100, type=int)
    entity_type = request.args.get("entity_type")
    action = request.args.get("action")

    # Build query
    query = AuditLog.query

    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if action:
        query = query.filter_by(action=action)

    # Get entries
    entries = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    return render_template("audit.html", entries=entries, limit=limit)


if __name__ == "__main__":
    import os

    init_db()
    # Always use debug=False for security
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=False, host="0.0.0.0", port=port)
