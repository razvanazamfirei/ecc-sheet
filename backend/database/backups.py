"""Database file backup helpers."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pytz

from backend.config import Config

logger = logging.getLogger("ecc_sheet")


def backup_database(
    db_path: str | Path = Path("ecc_sheet.db"),
    backup_dir: str | Path = Path("backups"),
) -> bool:
    """Create a timestamped SQLite database backup."""
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    tz = pytz.timezone(Config.TIMEZONE)
    timestamp = datetime.now(tz=tz).strftime("%Y%m%d_%H%M%S")
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"ecc_sheet_{timestamp}.db"
        with (
            sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True) as source,
            sqlite3.connect(str(backup_path)) as dest,
        ):
            source.backup(dest)
        prune_database_backups(backup_dir)
        return True
    except (OSError, sqlite3.OperationalError):
        logger.exception("Database backup failed")
        return False


def prune_database_backups(backup_dir: str | Path = Path("backups")) -> None:
    """Keep only the most recent 30 database backup files."""
    backup_path = Path(backup_dir)
    backups = sorted(
        f for f in backup_path.iterdir() if f.name.startswith("ecc_sheet_")
    )
    for old_backup in backups[:-30]:
        old_backup.unlink()
