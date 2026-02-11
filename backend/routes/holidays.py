"""Holiday management routes."""

from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..audit import log_create, log_delete
from ..auth import admin_required
from ..holidays import get_federal_holidays
from ..models import Holiday, db
from ..utils import get_effective_date

bp = Blueprint("holidays", __name__)


@bp.route("/holidays")
@admin_required
def index():
    """Manage holidays."""
    all_holidays = Holiday.query.order_by(Holiday.date).all()
    return render_template("holidays.html", holidays=all_holidays)


@bp.route("/holidays/add", methods=["POST"])
@admin_required
def add():
    """Add a custom holiday."""
    try:
        date_str = request.form.get("date")
        name = request.form.get("name", "").strip()

        if not date_str or not name:
            flash("Date and name are required", "error")
            return redirect(url_for("holidays.index"))

        holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()  # noqa: DTZ007

        # Check if holiday already exists
        if Holiday.query.filter_by(date=holiday_date).first():
            flash(f"Holiday already exists for {date_str}", "error")
            return redirect(url_for("holidays.index"))

        holiday = Holiday(
            date=holiday_date,
            name=name,
            is_federal=False,
        )
        db.session.add(holiday)
        db.session.commit()

        log_create("Holiday", holiday.id, {"date": date_str, "name": name})
        flash(f"Holiday '{name}' added successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error adding holiday: {e!s}", "error")

    return redirect(url_for("holidays.index"))


@bp.route("/holidays/<int:holiday_id>/delete", methods=["POST"])
@admin_required
def delete(holiday_id):
    """Delete a holiday."""
    holiday = db.session.get(Holiday, holiday_id)
    if holiday is None:
        abort(404)

    try:
        log_delete(
            "Holiday", holiday.id, {"date": str(holiday.date), "name": holiday.name}
        )
        db.session.delete(holiday)
        db.session.commit()
        flash(f"Holiday '{holiday.name}' deleted successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting holiday: {e!s}", "error")

    return redirect(url_for("holidays.index"))


@bp.route("/holidays/refresh", methods=["POST"])
@admin_required
def refresh_federal():
    """Refresh federal holidays for current and next year."""
    try:
        current_year = get_effective_date().year
        added = 0

        for year in [current_year, current_year + 1]:
            for holiday_date, holiday_name in get_federal_holidays(year):
                if not Holiday.query.filter_by(date=holiday_date).first():
                    holiday = Holiday(
                        date=holiday_date,
                        name=holiday_name,
                        is_federal=True,
                    )
                    db.session.add(holiday)
                    added += 1

        db.session.commit()

        if added > 0:
            flash(f"Added {added} federal holidays", "success")
        else:
            flash("All federal holidays are already present", "info")

    except Exception as e:
        db.session.rollback()
        flash(f"Error refreshing holidays: {e!s}", "error")

    return redirect(url_for("holidays.index"))
