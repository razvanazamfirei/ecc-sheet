#!/usr/bin/env python3
"""
Auto-Lock Checker for ECC Sheet
Automatically locks sheets at 9 AM based on configured timezone.

Usage: Run this script via cron every minute between 8-9 AM:
    * 8-9 * * * /path/to/.venv/bin/python /path/to/scripts/check_autolock.py
"""

import sys
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.app import app, db
from backend.audit import log_action
from backend.models import DailySheet
from backend.utils import get_effective_date

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path is set


def should_auto_lock():
    """Check if it's time to auto-lock sheets (9 AM)"""
    # Get current time in Philadelphia timezone

    philly_tz = ZoneInfo("America/New_York")
    now = datetime.now(philly_tz)

    # Auto-lock time is 9:00 AM
    auto_lock_time = time(9, 0)

    # Only run between 9:00 and 9:01 AM to avoid multiple runs
    return auto_lock_time <= now.time() < time(9, 1)


def auto_lock_sheets():
    """Auto-lock all unlocked sheets for dates before today"""
    with app.app_context():
        today = get_effective_date()

        # Find all unlocked sheets before today
        unlocked_sheets = DailySheet.query.filter(
            DailySheet.date < today, DailySheet.locked.is_(False)
        ).all()

        locked_count = 0
        for sheet in unlocked_sheets:
            sheet.locked = True
            sheet.locked_by = "System Auto-Lock"
            sheet.locked_at = datetime.now(UTC)

            # Log the auto-lock
            log_action(
                action="LOCK",
                entity_type="DailySheet",
                entity_id=sheet.id,
                details={"date": str(sheet.date), "auto_locked": True},
                user="system",
            )

            locked_count += 1

        if locked_count > 0:
            db.session.commit()
            print(f"Auto-locked {locked_count} sheet(s)")
        else:
            print("No sheets to auto-lock")

        return locked_count


def main():
    """Main function"""
    try:
        if should_auto_lock():
            print(f"Running auto-lock check at {datetime.now(UTC)}")
            auto_lock_sheets()
            sys.exit(0)
        else:
            # Not time yet, exit silently
            sys.exit(0)
    except Exception as e:
        print(f"Error during auto-lock: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
