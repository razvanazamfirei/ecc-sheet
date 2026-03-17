"""Helpers for limiting resident audit rows to payroll-impacting fields."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .models import Resident

PAYROLL_RESIDENT_FIELDS = frozenset({"name", "lawson_id", "hire_date"})


def filter_payroll_resident_changes(
    changes: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Return only resident changes that affect payroll exports."""
    if not changes:
        return {}

    return {
        field: dict(change)
        for field, change in changes.items()
        if field in PAYROLL_RESIDENT_FIELDS
    }


def payroll_resident_details(
    resident: Resident,
    **extra: Any,
) -> dict[str, Any]:
    """Return resident audit details limited to payroll-relevant fields."""
    details: dict[str, Any] = {
        "name": resident.name,
        "lawson_id": resident.lawson_id,
        "hire_date": resident.hire_date.isoformat() if resident.hire_date else None,
    }
    details.update(extra)
    return details
