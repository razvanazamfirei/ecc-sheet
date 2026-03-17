"""Shared helpers for route modules."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from logging import Logger
from typing import Any

from flask import flash, redirect, url_for
from werkzeug.wrappers import Response

from ..db_session import commit_or_rollback
from ..models import db
from ..parsing import parse_iso_date

__all__ = [
    "commit_flash_redirect",
    "diff_snapshots",
    "flash_message",
    "flash_redirect",
    "flash_sheet_redirect",
    "parse_iso_date",
    "parse_iso_date_or_none",
    "redirect_to",
    "rollback_flash_redirect",
]


def redirect_to(endpoint: str, /, **values: Any) -> Response:
    """Return a redirect to a Flask endpoint."""
    return redirect(url_for(endpoint, **values))


def flash_redirect(
    endpoint: str,
    message: str,
    category: str = "error",
    /,
    **values: Any,
) -> Response:
    """Flash a message and redirect to a Flask endpoint."""
    flash_message(message, category)
    return redirect_to(endpoint, **values)


def flash_message(message: str, category: str = "error") -> None:
    """Flash a message without creating a response object."""
    flash(message, category)


def flash_sheet_redirect(
    date_str: str,
    message: str,
    category: str = "error",
) -> Response:
    """Flash a message and redirect to a specific sheet."""
    return flash_redirect("sheets.view", message, category, date_str=date_str)


def parse_iso_date_or_none(
    raw: str,
    *,
    message: str = "Invalid date format",
) -> date | None:
    """Parse an ISO date string or flash and return None on failure."""
    try:
        return parse_iso_date(raw, error_message=message)
    except ValueError:
        flash_message(message, "error")
        return None


def rollback_flash_redirect(
    endpoint: str,
    message: str,
    category: str = "error",
    /,
    **values: Any,
) -> Response:
    """Rollback the current transaction, flash a message, and redirect."""
    db.session.rollback()
    return flash_redirect(endpoint, message, category, **values)


def commit_flash_redirect[T](
    mutation: Callable[[], T],
    *,
    endpoint: str,
    logger: Logger,
    errors: tuple[str, str],
    success_message: str | tuple[str, str] | Callable[[T], str | tuple[str, str]],
    **values: Any,
) -> Response:
    """Run a mutation, commit it, and redirect with a flashed message."""
    try:
        result = commit_or_rollback(mutation)
    except Exception:
        log_message, error_message = errors
        logger.exception(log_message)
        return flash_redirect(endpoint, error_message, "error", **values)

    outcome = success_message(result) if callable(success_message) else success_message
    if isinstance(outcome, tuple):
        message, category = outcome
    else:
        message, category = outcome, "success"

    return flash_redirect(endpoint, message, category, **values)


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
