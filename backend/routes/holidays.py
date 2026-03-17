"""Holiday management routes."""

import logging
from datetime import date
from logging import Logger

from flask import Blueprint, abort, render_template

from ..audit import log_create_strict, log_delete_strict, log_import_strict
from ..auth import admin_required
from ..holidays import get_federal_holidays
from ..models import Holiday, db
from ..utils import get_effective_date
from ._forms import form_text
from ._helpers import (
    commit_flash_redirect,
    flash_message,
    flash_redirect,
    parse_iso_date_or_none,
    redirect_to,
)

bp: Blueprint = Blueprint("holidays", __name__)
logger: Logger = logging.getLogger(__name__)


def _parse_holiday_form() -> tuple[str, str, date] | None:
    """Parse the add-holiday form values or flash an error."""
    date_str = form_text("date")
    name = form_text("name")
    if not date_str or not name:
        flash_message("Date and name are required")
        return None
    if (holiday_date := parse_iso_date_or_none(date_str)) is None:
        return None
    return date_str, name, holiday_date


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
        return flash_redirect(
            "holidays.index",
            f"Holiday already exists for {date_str}",
            "error",
        )

    def _save() -> None:
        holiday = Holiday(date=holiday_date, name=name, is_federal=False)
        db.session.add(holiday)
        db.session.flush()
        log_create_strict("Holiday", holiday.id, {"date": date_str, "name": name})

    return commit_flash_redirect(
        _save,
        endpoint="holidays.index",
        logger=logger,
        errors=("Error adding holiday", "Error adding holiday."),
        success_message=f"Holiday '{name}' added successfully",
    )


@bp.route("/holidays/<int:holiday_id>/delete", methods=["POST"])
@admin_required
def delete(holiday_id):
    """Delete a holiday."""
    holiday = db.session.get(Holiday, holiday_id)
    if holiday is None:
        abort(404)

    def _delete() -> None:
        log_delete_strict(
            "Holiday",
            holiday.id,
            {"date": str(holiday.date), "name": holiday.name},
        )
        db.session.delete(holiday)

    return commit_flash_redirect(
        _delete,
        endpoint="holidays.index",
        logger=logger,
        errors=("Error deleting holiday", "Error deleting holiday."),
        success_message=f"Holiday '{holiday.name}' deleted successfully",
    )


@bp.route("/holidays/refresh", methods=["POST"])
@admin_required
def refresh_federal():
    """Refresh federal holidays for current and next year."""
    current_year = get_effective_date().year

    def _refresh() -> int:
        created_holidays = _new_federal_holidays(current_year)
        db.session.add_all(created_holidays)
        db.session.flush()

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
        if created_holidays:
            log_import_strict(
                "Holiday",
                (
                    f"Refreshed federal holidays for {current_year} and "
                    f"{current_year + 1}; added {len(created_holidays)}"
                ),
            )
        return len(created_holidays)

    return commit_flash_redirect(
        _refresh,
        endpoint="holidays.index",
        logger=logger,
        errors=("Error refreshing holidays", "Error refreshing holidays."),
        success_message=(
            lambda added: (
                (f"Added {added} federal holidays", "success")
                if added
                else ("All federal holidays are already present", "info")
            )
        ),
    )
