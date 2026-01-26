"""
Holiday utilities for overtime calculation.

Uses the 'holidays' library for US federal holidays.
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
    Check if a date is a weekend or holiday.

    Args:
        check_date: The date to check

    Returns:
        True if the date is a weekend or holiday
    """
    us_holidays = holidays.US(years=[check_date.year])
    return not us_holidays.is_working_day(check_date)
