"""Route blueprints for the application."""

from . import (
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
from ._registry import register_blueprints

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
