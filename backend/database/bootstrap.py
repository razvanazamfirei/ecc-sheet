"""Database bootstrap tasks for schema and default data."""

from __future__ import annotations

import logging
from collections.abc import Callable

from flask import Flask

from backend.config import (
    BACKUP_ROLE_NAMES,
    CALL_TEAM_ROLE_NAMES,
    DEFAULT_CUTOFF_HOUR,
    DEFAULT_CUTOFF_MINUTE,
    DEFAULT_ROLES,
    ROLE_CUTOFF_HOURS,
    ROLE_CUTOFF_MINUTES,
)
from backend.database.runtime_schema import ensure_runtime_schema as _ensure_schema
from backend.holidays import get_federal_holidays
from backend.models import Holiday, Role, db
from backend.utils import get_effective_date

logger = logging.getLogger(__name__)


def init_db(
    app: Flask,
    *,
    ensure_runtime_schema: Callable[[], None] | None = None,
) -> None:
    """Initialize schema, default roles, and current federal holidays."""
    with app.app_context():
        if ensure_runtime_schema is None:
            _ensure_schema(app, logger=logger)
        else:
            ensure_runtime_schema()

        for role_name, order in DEFAULT_ROLES:
            existing_role = Role.query.filter_by(name=role_name).first()
            if not existing_role:
                cutoff_hour = ROLE_CUTOFF_HOURS.get(role_name, DEFAULT_CUTOFF_HOUR)
                cutoff_minute = ROLE_CUTOFF_MINUTES.get(
                    role_name, DEFAULT_CUTOFF_MINUTE
                )
                role = Role(
                    name=role_name,
                    cutoff_hour=cutoff_hour,
                    cutoff_minute=cutoff_minute,
                    display_order=order,
                    is_backup=(role_name in BACKUP_ROLE_NAMES),
                    is_call_team=(role_name in CALL_TEAM_ROLE_NAMES),
                )
                db.session.add(role)
            else:
                # Always correct categorical flags; only backfill display_order
                # if unset so admin-customized ordering is preserved.
                existing_role.is_backup = role_name in BACKUP_ROLE_NAMES
                existing_role.is_call_team = role_name in CALL_TEAM_ROLE_NAMES
                if existing_role.display_order is None:
                    existing_role.display_order = order

        current_year = get_effective_date().year
        for year in [current_year, current_year + 1]:
            for holiday_date, holiday_name in get_federal_holidays(year):
                if not Holiday.query.filter_by(date=holiday_date).first():
                    holiday = Holiday(
                        date=holiday_date,
                        name=holiday_name,
                        is_federal=True,
                    )
                    db.session.add(holiday)

        db.session.commit()
