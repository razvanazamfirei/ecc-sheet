"""Shared parsing helpers used across routes and backend services."""

from __future__ import annotations

from datetime import date


def parse_iso_date(raw: str, *, error_message: str = "Invalid date format") -> date:
    """Parse an ISO date string or raise ValueError with a caller-supplied message."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(error_message) from exc
