"""Shared normalization helpers for resident import workflows."""

from __future__ import annotations

from collections.abc import Mapping

from email_validator import validate_email

CLASS_YEAR_ALIASES: dict[str, str] = {
    "ca1": "CA-1",
    "ca-1": "CA-1",
    "ca2": "CA-2",
    "ca-2": "CA-2",
    "ca3": "CA-3",
    "ca-3": "CA-3",
    "fellow": "Fellow",
    "omfs": "OMFS",
}


def clean_text(value: str | None) -> str:
    """Return a trimmed string, defaulting missing values to empty."""
    return value.strip() if value else ""


def split_name(name: str) -> tuple[str | None, str | None]:
    """Split a full name into first and last components."""
    parts = clean_text(name).rsplit(" ", 1)
    if not parts or not parts[0]:
        return None, None
    first_name = parts[0].strip() or None
    last_name = parts[1].strip() if len(parts) > 1 else None
    return first_name, last_name or None


def normalize_email(value: str) -> str | None:
    """Validate and normalize an email value."""
    if not (normalized := clean_text(value)):
        return None
    return validate_email(
        normalized,
        check_deliverability=False,
    ).normalized.lower()


def canonicalize_class_year(
    value: str,
    aliases: Mapping[str, str] | None = None,
) -> str | None:
    """Return a normalized class-year alias, preserving unknown values."""
    if not (normalized := clean_text(value)):
        return None
    return (CLASS_YEAR_ALIASES if aliases is None else aliases).get(
        normalized.casefold(),
        normalized,
    )
