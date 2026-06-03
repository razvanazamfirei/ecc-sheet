"""Utility functions for logging and validation."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz
from email_validator import validate_email
from flask import request

from backend.config import Config

logger = logging.getLogger("ecc_sheet")


def wants_json_response() -> bool:
    """Return True when the caller expects a JSON response."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("X-Expect-JSON") == "1"
        or "application/json" in request.headers.get("Accept", "")
    )


def setup_logging() -> logging.Logger:
    """Configure application logging"""
    log_dir: Path = Path("logs")
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    tz = pytz.timezone(Config.TIMEZONE)
    log_file: Path = log_dir / f"ecc_sheet_{datetime.now(tz=tz).strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )

    return logging.getLogger("ecc_sheet")


def get_philadelphia_time() -> datetime:
    """Get current time in Philadelphia timezone."""
    philly_tz = pytz.timezone(Config.TIMEZONE)
    return datetime.now(philly_tz)


def get_effective_date(dt: datetime | None = None) -> date:
    """
    Get the effective date for a given datetime in Philadelphia time.
    Day resets at 8 AM - times before 8 AM belong to the previous calendar day.

    Args:
        dt: datetime object (if None, uses current Philadelphia time)

    Returns:
        date object representing the effective day
    """
    if dt is None:
        dt = get_philadelphia_time()

    # Ensure datetime is in Philadelphia timezone
    philly_tz = pytz.timezone(Config.TIMEZONE)
    if dt.tzinfo is None:
        dt = philly_tz.localize(dt)
    elif dt.tzinfo != philly_tz:
        dt = dt.astimezone(philly_tz)

    # If before 8 AM, use previous day
    reset_hour: int = Config.DAY_RESET_HOUR
    if dt.hour < reset_hour:
        return (dt - timedelta(days=1)).date()

    return dt.date()


def normalize_email(address: str) -> str:
    """Validate and normalize a single email address."""
    return validate_email(address.strip(), check_deliverability=False).normalized


def parse_iso_date(raw: str, *, error_message: str = "Invalid date format") -> date:
    """Parse an ISO date string or raise ValueError with a caller-supplied message."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(error_message) from exc
