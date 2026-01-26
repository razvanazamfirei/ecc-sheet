"""
Holiday utilities for overtime calculation.

Uses the 'holidays' library for US federal holidays and checks custom holidays
from the database.
"""

from datetime import date

import holidays


def get_federal_holidays(year: int) -> list[tuple[date, str]]:
    """
    Get all US federal holidays for a given year.

    Args:
        year: The year to get holidays for

    Returns:
        List of (date, name) tuples for each holiday
    """
    us_holidays = holidays.US(years=[year])
    return [(d, name) for d, name in sorted(us_holidays.items())]


def is_weekend_or_holiday(check_date: date) -> bool:
    """
    Check if a date is a weekend or US federal holiday or custom holiday.

    Args:
        check_date: The date to check

    Returns:
        True if the date is a weekend, federal holiday, or custom holiday
    """
    # Import here to avoid circular import (Holiday model imports this module)
    from .models import Holiday

    # Check US federal holidays and weekends
    us_holidays = holidays.US(years=[check_date.year])
    if not us_holidays.is_working_day(check_date):
        return True

    # Check custom holidays from database
    return Holiday.is_holiday(check_date)
