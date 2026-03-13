"""Shared helpers for route modules."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from flask import redirect, url_for
from werkzeug.wrappers import Response


def redirect_to(endpoint: str, /, **values: Any) -> Response:
    """Return a redirect to a Flask endpoint."""
    return redirect(url_for(endpoint, **values))


def sheet_view_redirect(date_str: str) -> Response:
    """Return a redirect to a specific sheet."""
    return redirect_to("sheets.view", date_str=date_str)


def parse_iso_date(raw: str, *, error_message: str = "Invalid date format") -> date:
    """Parse an ISO date string or raise ValueError with a route-friendly message."""
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(error_message) from exc


def diff_snapshots(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return old/new values for all fields that changed between snapshots."""
    return {
        field: {"old": before[field], "new": after[field]}
        for field in before
        if before[field] != after[field]
    }
