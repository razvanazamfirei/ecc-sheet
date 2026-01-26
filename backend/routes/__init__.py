"""Route blueprints for the application."""

from . import api, audit, entries, holidays, reports, residents, roles, schedule, sheets
from ._registry import register_blueprints

__all__ = [
    "api",
    "audit",
    "entries",
    "holidays",
    "register_blueprints",
    "reports",
    "residents",
    "roles",
    "schedule",
    "sheets",
]
