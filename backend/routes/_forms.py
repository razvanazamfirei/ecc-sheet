"""Shared form parsing helpers for route handlers."""

from __future__ import annotations

from datetime import date

from flask import request

from ..parsing import parse_iso_date


def form_text(key: str) -> str:
    """Return a trimmed form value."""
    return request.form.get(key, "").strip()


def optional_form_text(key: str) -> str | None:
    """Return a trimmed optional form value."""
    return form_text(key) or None


def optional_form_int(key: str) -> int | None:
    """Return an optional integer form value."""
    value = form_text(key)
    if not value:
        return None
    return int(value)


def optional_form_iso_date(key: str) -> date | None:
    """Return an optional ISO date form value."""
    value = form_text(key)
    if not value:
        return None
    return parse_iso_date(value)
