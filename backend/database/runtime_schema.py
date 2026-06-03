"""Runtime schema bootstrapping helpers."""

from __future__ import annotations

import logging
import threading

from flask import Flask
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.database.session import commit_or_rollback
from backend.models import db

_runtime_schema_lock = threading.Lock()


def is_duplicate_column_error(exc: SQLAlchemyError, column_name: str) -> bool:
    """Return True when a schema ALTER failed because the column already exists."""
    messages = [str(exc)]
    original_error = getattr(exc, "orig", None)
    if original_error is not None and original_error is not exc:
        messages.append(str(original_error))

    normalized_message = " ".join(messages).casefold()
    normalized_column = column_name.casefold()
    duplicate_markers = ("duplicate column", "already exists")
    return normalized_column in normalized_message and any(
        marker in normalized_message for marker in duplicate_markers
    )


def ensure_time_entry_columns(logger: logging.Logger | None = None) -> None:
    """Backfill nullable TimeEntry columns for existing databases."""
    inspector = sqlalchemy_inspect(db.engine)
    time_entry_columns = {
        column["name"] for column in inspector.get_columns("time_entries")
    }
    if "anesthesia_stop_time" in time_entry_columns:
        return

    try:
        commit_or_rollback(
            lambda: db.session.execute(
                text("ALTER TABLE time_entries ADD COLUMN anesthesia_stop_time TIME")
            )
        )
    except SQLAlchemyError as exc:
        if is_duplicate_column_error(exc, "anesthesia_stop_time"):
            if logger is not None:
                logger.info(
                    "Column anesthesia_stop_time already exists; "
                    "skipping runtime schema backfill.",
                )
            return
        raise


def ensure_runtime_schema(app: Flask, logger: logging.Logger | None = None) -> None:
    """Ensure required tables and additive columns exist for this process."""
    with _runtime_schema_lock:
        if app.extensions.get("runtime_schema_checked"):
            return

        db.create_all()
        ensure_time_entry_columns(logger=logger)
        app.extensions["runtime_schema_checked"] = True
