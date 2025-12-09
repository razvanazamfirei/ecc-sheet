"""
Audit logging utilities for tracking all changes in the system.
"""

import json
from datetime import UTC, datetime

from flask import current_app, request

from .models import AuditLog, db


def get_current_user():
    """Get the current user from session or config"""
    # In a real app, you'd get this from session/auth
    # For now, use the config value
    return current_app.config.get("USER_NAME", "System")


def get_client_ip():
    """Get the client's IP address"""
    if request:
        # Check for proxy headers first
        if request.headers.get("X-Forwarded-For"):
            return request.headers.get("X-Forwarded-For").split(",")[0].strip()
        if request.headers.get("X-Real-IP"):
            return request.headers.get("X-Real-IP")
        return request.remote_addr
    return None


def log_action(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
    user: str | None = None,
):
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
        db.session.commit()
    except Exception as e:
        # Don't let audit logging break the main flow
        print(f"Audit logging failed: {e!s}")
        db.session.rollback()


def log_create(entity_type: str, entity_id: int, details: dict | None = None):
    """Log a CREATE action"""
    log_action("CREATE", entity_type, entity_id, details)


def log_update(
    entity_type: str,
    entity_id: int,
    changes: dict | None = None,
    details: dict | None = None,
):
    """Log an UPDATE action"""
    if changes:
        details = details or {}
        details["changes"] = changes
    log_action("UPDATE", entity_type, entity_id, details)


def log_delete(entity_type: str, entity_id: int, details: dict | None = None):
    """Log a DELETE action"""
    log_action("DELETE", entity_type, entity_id, details)


def log_lock(sheet_date: str, locked: bool):
    """Log a lock/unlock action"""
    action = "LOCK" if locked else "UNLOCK"
    log_action(action, "DailySheet", details={"date": sheet_date})


def log_import(
    import_type: str,
    details_str: str,
    user: str | None = None,
    entity_id: int | None = None,
):
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
):
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


def get_entity_history(entity_type: str, entity_id: int):
    """Get the full history of changes for a specific entity"""
    return get_audit_trail(entity_type=entity_type, entity_id=entity_id, limit=1000)
