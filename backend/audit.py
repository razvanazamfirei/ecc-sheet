"""
Audit logging utilities for tracking all changes in the system.
"""

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from flask import has_request_context, request
from sqlalchemy import insert

from backend.auth import get_current_user
from backend.models import AuditLog, db
from backend.type_defs import AuditLogs

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


def _build_audit_values(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> dict[str, Any]:
    """Build a normalized audit-log payload."""
    details_json = json.dumps(details) if details else None
    return {
        "timestamp": datetime.now(UTC),
        "user": user or get_current_user(),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details_json,
        "ip_address": get_client_ip(),
    }


def _write_audit_log(audit_values: Mapping[str, Any], *, strict: bool = False) -> None:
    """Persist an audit log entry."""
    try:
        db.session.execute(insert(AuditLog).values(**audit_values))
    except Exception:
        logger.exception("Audit logging failed")
        if strict:
            raise


def _update_details(
    changes: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Merge explicit details with an optional change map."""
    merged_details = dict(details) if details else {}
    if changes:
        merged_details["changes"] = dict(changes)
    return merged_details or None


def _lock_action(locked: bool) -> str:
    """Return the audit action for a sheet lock state."""
    return "LOCK" if locked else "UNLOCK"


def log_action(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> None:
    """Log an action to the audit trail without interrupting the caller."""
    _write_audit_log(_build_audit_values(action, entity_type, entity_id, details, user))


def log_action_strict(
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> None:
    """Log an action and re-raise failures so the caller can roll back."""
    _write_audit_log(
        _build_audit_values(action, entity_type, entity_id, details, user),
        strict=True,
    )


def log_create(
    entity_type: str,
    entity_id: int,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Log a CREATE action"""
    log_action("CREATE", entity_type, entity_id, details)


def log_create_strict(
    entity_type: str,
    entity_id: int,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Log a CREATE action and re-raise failures."""
    log_action_strict("CREATE", entity_type, entity_id, details)


def log_update(
    entity_type: str,
    entity_id: int,
    changes: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> None:
    """Log an UPDATE action"""
    log_action(
        "UPDATE",
        entity_type,
        entity_id,
        _update_details(changes, details),
        user=user,
    )


def log_update_strict(
    entity_type: str,
    entity_id: int,
    changes: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    user: str | None = None,
) -> None:
    """Log an UPDATE action and re-raise failures."""
    log_action_strict(
        "UPDATE",
        entity_type,
        entity_id,
        _update_details(changes, details),
        user=user,
    )


def log_delete(
    entity_type: str,
    entity_id: int,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Log a DELETE action"""
    log_action("DELETE", entity_type, entity_id, details)


def log_delete_strict(
    entity_type: str,
    entity_id: int,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Log a DELETE action and re-raise failures."""
    log_action_strict("DELETE", entity_type, entity_id, details)


def log_lock(sheet_date: str, *, locked: bool) -> None:
    """Log a lock/unlock action"""
    log_action(_lock_action(locked), "DailySheet", details={"date": sheet_date})


def log_lock_strict(sheet_date: str, *, locked: bool) -> None:
    """Log a lock/unlock action and re-raise failures."""
    log_action_strict(_lock_action(locked), "DailySheet", details={"date": sheet_date})


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


def log_import_strict(
    import_type: str,
    details_str: str,
    user: str | None = None,
    entity_id: int | None = None,
) -> None:
    """Log an import action and re-raise failures."""
    log_action_strict(
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
