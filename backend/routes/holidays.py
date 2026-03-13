"""Holiday management routes."""

import logging
from datetime import date
from logging import Logger

from flask import Blueprint, abort, flash, render_template

from ..audit import log_create_strict, log_delete_strict, log_import_strict
from ..auth import admin_required
from ..holidays import get_federal_holidays
from ..models import Holiday, db
from ..utils import get_effective_date
from ._forms import form_text
from ._helpers import parse_iso_date, redirect_to

bp: Blueprint = Blueprint("holidays", __name__)
logger: Logger = logging.getLogger(__name__)


def _holiday_error(message: str) -> None:
    """Rollback a failed holiday mutation and flash a generic error."""
    db.session.rollback()
    flash(message, "error")


def _parse_holiday_form() -> tuple[str, str, date] | None:
    """Parse the add-holiday form values or flash an error."""
    date_str = form_text("date")
    name = form_text("name")
    if not date_str or not name:
        flash("Date and name are required", "error")
        return None
    try:
        return date_str, name, parse_iso_date(date_str)
    except ValueError:
        flash("Invalid date format", "error")
        return None


def _new_federal_holidays(current_year: int) -> list[Holiday]:
    """Return federal holidays missing from the current and next year."""
    holidays_to_create: list[Holiday] = []
    for year in range(current_year, current_year + 2):
        for holiday_date, holiday_name in get_federal_holidays(year):
            if Holiday.query.filter_by(date=holiday_date).first():
                continue

            holidays_to_create.append(
                Holiday(
                    date=holiday_date,
                    name=holiday_name,
                    is_federal=True,
                )
            )

    return holidays_to_create


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
    parsed_form = _parse_holiday_form()
    if parsed_form is None:
        return redirect_to("holidays.index")

    date_str, name, holiday_date = parsed_form

    if Holiday.query.filter_by(date=holiday_date).first():
        flash(f"Holiday already exists for {date_str}", "error")
        return redirect_to("holidays.index")

    try:
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
    except Exception:
        logger.exception("Error adding holiday")
        _holiday_error("Error adding holiday.")

    return redirect_to("holidays.index")


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

    except Exception:
        logger.exception("Error deleting holiday")
        _holiday_error("Error deleting holiday.")

    return redirect_to("holidays.index")


@bp.route("/holidays/refresh", methods=["POST"])
@admin_required
def refresh_federal():
    """Refresh federal holidays for current and next year."""
    try:
        current_year = get_effective_date().year
        created_holidays = _new_federal_holidays(current_year)
        added = len(created_holidays)
        db.session.add_all(created_holidays)

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

    except Exception:
        logger.exception("Error refreshing holidays")
        _holiday_error("Error refreshing holidays.")

    return redirect_to("holidays.index")
