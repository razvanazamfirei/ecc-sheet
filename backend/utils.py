"""
Utility functions for logging, validation, and error handling
"""

import logging
import shutil
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import pytz
from flask import flash, redirect, url_for

from .config import Config
from .models import db

logger = logging.getLogger("ecc_sheet")


def setup_logging():
    """Configure application logging"""
    log_dir = Path("logs")
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)

    tz = pytz.timezone(Config.TIMEZONE)
    log_file = log_dir / f"ecc_sheet_{datetime.now(tz=tz).strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )

    return logging.getLogger("ecc_sheet")


def backup_database(db_path: Path = "ecc_sheet.db", backup_dir: Path = "backups"):
    """Create a backup of the database"""
    try:
        backup_dir = Path(backup_dir)
        db_path = Path(db_path)

        if not backup_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)

        if not db_path.exists():
            return False

        tz = pytz.timezone(Config.TIMEZONE)
        timestamp = datetime.now(tz=tz).strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"ecc_sheet_{timestamp}.db"

        shutil.copy2(db_path, backup_path)

        # Keep only last 30 backups
        backups = sorted(
            [f for f in backup_dir.iterdir() if f.name.startswith("ecc_sheet_")]
        )
        if len(backups) > 30:
            for old_backup in backups[:-30]:
                old_backup.unlink()

        return True
    except Exception as e:
        logger.error("Database backup failed: %s", e)
        return False


def handle_db_error(func):
    """Decorator for handling database errors gracefully"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error("Database error in %s: %s", func.__name__, e)
            db.session.rollback()
            flash(f"An error occurred: {e!s}", "error")
            return redirect(url_for("index"))

    return wrapper


def get_philadelphia_time():
    """Get current time in Philadelphia timezone"""
    philly_tz = pytz.timezone(Config.TIMEZONE)
    return datetime.now(philly_tz)


def get_effective_date(dt=None):
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
    reset_hour = Config.DAY_RESET_HOUR
    if dt.hour < reset_hour:
        return (dt - timedelta(days=1)).date()

    return dt.date()


def philly_now():
    """Convenience function to get current Philadelphia datetime"""
    return get_philadelphia_time()


def philly_today():
    """Get today's effective date in Philadelphia time (accounting for 8 AM reset)"""
    return get_effective_date()
