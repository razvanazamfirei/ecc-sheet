"""Database file backup helpers."""

from __future__ import annotations

import logging
import shutil
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
        if not db_path.exists():
            return False

        shutil.copy2(db_path, backup_dir / f"ecc_sheet_{timestamp}.db")
        prune_database_backups(backup_dir)
        return True
    except OSError:
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
