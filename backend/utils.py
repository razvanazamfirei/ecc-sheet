"""Utility functions for logging and validation."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz
from email_validator import validate_email
from flask import request

from backend.config import Config

logger = logging.getLogger("ecc_sheet")

CLASS_YEAR_ALIASES: dict[str, str] = {
    "ca1": "CA-1",
    "ca-1": "CA-1",
    "ca2": "CA-2",
    "ca-2": "CA-2",
    "ca3": "CA-3",
    "ca-3": "CA-3",
    "fellow": "Fellow",
    "omfs": "OMFS",
}


def wants_json_response() -> bool:
    """Return True when the caller expects a JSON response."""
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.headers.get("X-Expect-JSON") == "1"
        or "application/json" in request.headers.get("Accept", "")
    )


def clean_text(value: str | None) -> str:
    """Return a trimmed string, defaulting missing values to empty."""
    return value.strip() if value else ""


def split_name(name: str) -> tuple[str | None, str | None]:
    """Split a full name into first and last components."""
    parts = clean_text(name).rsplit(" ", 1)
    if not parts or not parts[0]:
        return None, None
    first_name = parts[0].strip() or None
    last_name = parts[1].strip() if len(parts) > 1 else None
    return first_name, last_name or None


def canonicalize_class_year(
    value: str,
    aliases: Mapping[str, str] | None = None,
) -> str | None:
    """Return a normalized class-year alias, preserving unknown values."""
    if not (normalized := clean_text(value)):
        return None
    return (CLASS_YEAR_ALIASES if aliases is None else aliases).get(
        normalized.casefold(),
        normalized,
    )


def normalize_name_for_matching(raw_name: str) -> str:
    """Normalize whitespace and case in a person name for matching."""
    return " ".join(raw_name.split()).casefold()


def name_match_keys(raw_name: str) -> set[str]:
    """Return common first/last and last/comma/first match keys for a name."""
    normalized = normalize_name_for_matching(raw_name)
    if not normalized:
        return set()

    keys = {normalized}
    if "," in normalized:
        last_name, remainder = (part.strip() for part in normalized.split(",", 1))
        first_tokens = remainder.split()
        if first_tokens:
            first_name = first_tokens[0]
            keys.add(f"{last_name}, {first_name}")
            keys.add(f"{first_name} {last_name}")
        return keys

    name_parts = normalized.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = name_parts[-1]
        keys.add(f"{first_name} {last_name}")
        keys.add(f"{last_name}, {first_name}")
    return keys


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


def backup_database(
    db_path: str | Path = Path("ecc_sheet.db"),
    backup_dir: str | Path = Path("backups"),
) -> bool:
    """Create a backup of the database"""
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    tz = pytz.timezone(Config.TIMEZONE)
    timestamp = datetime.now(tz=tz).strftime("%Y%m%d_%H%M%S")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        if not db_path.exists():
            return False

        shutil.copy2(db_path, backup_dir / f"ecc_sheet_{timestamp}.db")
        _prune_database_backups(backup_dir)
        return True
    except OSError:
        logger.exception("Database backup failed")
        return False


def _prune_database_backups(backup_dir: Path) -> None:
    """Keep only the most recent 30 database backup files."""
    backups = sorted(f for f in backup_dir.iterdir() if f.name.startswith("ecc_sheet_"))
    for old_backup in backups[:-30]:
        old_backup.unlink()


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
