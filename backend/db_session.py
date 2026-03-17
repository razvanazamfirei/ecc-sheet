"""Small helpers for SQLAlchemy session commit/rollback flows."""

from __future__ import annotations

from collections.abc import Callable

from .models import db


def commit_or_rollback[T](operation: Callable[[], T]) -> T:
    """Run a unit of work, committing on success and rolling back on failure."""
    try:
        result = operation()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return result
