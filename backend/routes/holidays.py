"""Holiday management routes."""

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..audit import log_create_strict, log_delete_strict, log_import_strict
from ..auth import admin_required
from ..holidays import get_federal_holidays
from ..models import Holiday, db
from ..utils import get_effective_date

bp: Blueprint = Blueprint("holidays", __name__)


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

        holiday_date = date.fromisoformat(date_str)

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
        db.session.flush()
        log_create_strict(
            "Holiday",
            holiday.id,
            {"date": date_str, "name": name},
        )
        db.session.commit()
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
        log_details = {"date": str(holiday.date), "name": holiday.name}
        deleted_holiday_id = holiday.id
        deleted_holiday_name = holiday.name
        db.session.delete(holiday)
        log_delete_strict(
            "Holiday",
            deleted_holiday_id,
            log_details,
        )
        db.session.commit()
        flash(f"Holiday '{deleted_holiday_name}' deleted successfully", "success")

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
        created_holidays: list[Holiday] = []

        for year in [current_year, current_year + 1]:
            for holiday_date, holiday_name in get_federal_holidays(year):
                if not Holiday.query.filter_by(date=holiday_date).first():
                    holiday = Holiday(
                        date=holiday_date,
                        name=holiday_name,
                        is_federal=True,
                    )
                    db.session.add(holiday)
                    created_holidays.append(holiday)
                    added += 1

        db.session.flush()

        if added > 0:
            for holiday in created_holidays:
                log_create_strict(
                    "Holiday",
                    holiday.id,
                    {
                        "date": holiday.date.isoformat(),
                        "name": holiday.name,
                        "is_federal": holiday.is_federal,
                        "source": "federal_refresh",
                    },
                )
            log_import_strict(
                "Holiday",
                (
                    f"Refreshed federal holidays for {current_year} and "
                    f"{current_year + 1}; added {added}"
                ),
            )
            db.session.commit()
            flash(f"Added {added} federal holidays", "success")
        else:
            db.session.commit()
            flash("All federal holidays are already present", "info")

    except Exception as e:
        db.session.rollback()
        flash(f"Error refreshing holidays: {e!s}", "error")

    return redirect(url_for("holidays.index"))
