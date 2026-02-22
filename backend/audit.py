"""
Audit logging utilities for tracking all changes in the system.
"""

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from flask import has_request_context, request
from sqlalchemy.exc import SQLAlchemyError

from .auth import get_current_user
from .models import AuditLog, db
from .type_defs import AuditLogs

logger = logging.getLogger(__name__)


def get_client_ip() -> str | None:
    """Get the client's IP address."""
    if not has_request_context():
        return None

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    return request.remote_addr


def log_action(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> None:
    """
    Log an action to the audit trail.

    Args:
        action: Type of action (CREATE, UPDATE, DELETE, LOCK, UNLOCK, IMPORT, etc.)
        entity_type: Type of entity (TimeEntry, DailySheet, Resident, etc.)
        entity_id: ID of the entity being modified
        details: Dictionary of additional details to log
        user: User performing the action (defaults to current user)
    """
    try:
        audit_entry = AuditLog(
            timestamp=datetime.now(UTC),
            user=user or get_current_user(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=json.dumps(details) if details else None,
            ip_address=get_client_ip(),
        )
        db.session.add(audit_entry)
        db.session.flush()
    except SQLAlchemyError:
        # Don't let audit logging break the main flow; the caller's transaction
        # controls commit/rollback.
        logger.exception("Audit logging failed")


def log_create(
    entity_type: str, entity_id: int, details: Mapping[str, Any] | None = None
) -> None:
    """Log a CREATE action"""
    log_action("CREATE", entity_type, entity_id, details)


def log_update(
    entity_type: str,
    entity_id: int,
    changes: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Log an UPDATE action"""
    merged_details = dict(details) if details else {}
    if changes:
        merged_details["changes"] = dict(changes)
    log_action("UPDATE", entity_type, entity_id, merged_details or None)


def log_delete(
    entity_type: str, entity_id: int, details: Mapping[str, Any] | None = None
) -> None:
    """Log a DELETE action"""
    log_action("DELETE", entity_type, entity_id, details)


def log_lock(sheet_date: str, *, locked: bool) -> None:
    """Log a lock/unlock action"""
    action = "LOCK" if locked else "UNLOCK"
    log_action(action, "DailySheet", details={"date": sheet_date})


def log_import(
    import_type: str,
    details_str: str,
    user: str | None = None,
    entity_id: int | None = None,
) -> None:
    """
    Log an import action.

    Args:
        import_type: Type of import (e.g., "Schedule", "StaffList")
        details_str: Description of import results (e.g., "Created: 5, Updated: 10")
        user: User performing the import (defaults to current user)
        entity_id: Optional entity ID if applicable
    """
    log_action(
        "IMPORT",
        import_type,
        entity_id=entity_id,
        details={"info": details_str},
        user=user,
    )


def get_audit_trail(
    entity_type: str | None = None,
    entity_id: int | None = None,
    user: str | None = None,
    action: str | None = None,
    limit: int = 100,
) -> AuditLogs:
    """
    Get audit trail entries with optional filtering.

    Args:
        entity_type: Filter by entity type
        entity_id: Filter by entity ID
        user: Filter by user
        action: Filter by action type
        limit: Maximum number of entries to return

    Returns:
        List of AuditLog entries
    """
    query = AuditLog.query

    if entity_type:
        query = query.filter_by(entity_type=entity_type)
    if entity_id:
        query = query.filter_by(entity_id=entity_id)
    if user:
        query = query.filter_by(user=user)
    if action:
        query = query.filter_by(action=action)

    return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()


def get_entity_history(entity_type: str, entity_id: int) -> AuditLogs:
    """Get the full history of changes for a specific entity"""
    return get_audit_trail(entity_type=entity_type, entity_id=entity_id, limit=1000)
