"""Route blueprints for the application."""

from backend.routes import (
    api,
    audit,
    dev,
    entries,
    holidays,
    reports,
    residents,
    roles,
    schedule,
    sheets,
    sso,
)
from backend.routes._registry import register_blueprints

__all__ = [
    "api",
    "audit",
    "dev",
    "entries",
    "holidays",
    "register_blueprints",
    "reports",
    "residents",
    "roles",
    "schedule",
    "sheets",
    "sso",
]
