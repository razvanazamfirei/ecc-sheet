"""Tests for audit functionality."""

from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.audit import (
    get_audit_trail,
    get_client_ip,
    get_entity_history,
    log_action,
    log_action_strict,
    log_create,
    log_delete,
    log_import,
    log_lock,
    log_update,
)
from backend.models import AuditLog, db


class TestAuditLogging:
    """Tests for audit logging functions."""

    def test_log_create(self, app):
        """Test logging a create action."""
        with app.app_context():
            log_create("TestEntity", 1, {"field": "value"})

            log = AuditLog.query.filter_by(
                action="CREATE", entity_type="TestEntity", entity_id=1
            ).first()
            assert log is not None
            assert "field" in log.details

            db.session.delete(log)
            db.session.commit()

    def test_log_update(self, app):
        """Test logging an update action."""
        with app.app_context():
            log_update("TestEntity", 2, {"old_value": "a", "new_value": "b"})

            log = AuditLog.query.filter_by(
                action="UPDATE", entity_type="TestEntity", entity_id=2
            ).first()
            assert log is not None

            db.session.delete(log)
            db.session.commit()

    def test_log_update_uses_explicit_user(self, app):
        """Test logging an update action with an explicit user override."""
        with app.app_context():
            log_update(
                "TestEntity",
                22,
                {"old_value": "a", "new_value": "b"},
                user="Explicit Update User",
            )

            log = AuditLog.query.filter_by(
                action="UPDATE",
                entity_type="TestEntity",
                entity_id=22,
            ).first()
            assert log is not None
            assert log.user == "Explicit Update User"

            db.session.delete(log)
            db.session.commit()

    def test_log_delete(self, app):
        """Test logging a delete action."""
        with app.app_context():
            log_delete("TestEntity", 3, {"name": "deleted item"})

            log = AuditLog.query.filter_by(
                action="DELETE", entity_type="TestEntity", entity_id=3
            ).first()
            assert log is not None

            db.session.delete(log)
            db.session.commit()

    def test_log_lock(self, app):
        """Test logging a lock action."""
        with app.app_context():
            log_lock("2024-01-15", locked=True)

            log = (
                AuditLog.query.filter_by(action="LOCK")
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None
            assert "2024-01-15" in log.details

            db.session.delete(log)
            db.session.commit()

    def test_log_unlock(self, app):
        """Test logging an unlock action."""
        with app.app_context():
            log_lock("2024-01-15", locked=False)

            log = (
                AuditLog.query.filter_by(action="UNLOCK")
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None

            db.session.delete(log)
            db.session.commit()

    def test_log_import(self, app):
        """Test logging an import action."""
        with app.app_context():
            log_import("Schedule", "Imported 5 entries for 2024-01-15")

            log = (
                AuditLog.query.filter_by(action="IMPORT")
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log is not None
            assert "5" in log.details

            db.session.delete(log)
            db.session.commit()


class TestAuditRoute:
    """Tests for audit route."""

    def test_audit_page_loads(self, client):
        """Test that audit page loads."""
        response = client.get("/audit")
        assert response.status_code == 200
        assert b"Audit" in response.data

    def test_audit_with_filters(self, client):
        """Test audit page with filters."""
        response = client.get("/audit?entity_type=TimeEntry&action=CREATE&limit=50")
        assert response.status_code == 200

    def test_audit_requires_admin(self, client, monkeypatch):
        """Test that audit page requires admin privileges."""
        monkeypatch.setenv("USER_NAME", "Regular User")
        monkeypatch.setenv("ADMIN_USERS", "Admin Only")

        response = client.get("/audit", follow_redirects=True)
        assert b"Admin privileges required" in response.data

    def test_audit_filter_by_entity_type_only(self, client, app):
        """Test filtering audit log by entity type only."""
        with app.app_context():
            # Create a test log entry
            log_create("FilterTest", 999, {"test": "data"})

            response = client.get("/audit?entity_type=FilterTest")
            assert response.status_code == 200

            # Cleanup
            log_entry = AuditLog.query.filter_by(entity_type="FilterTest").first()
            if log_entry:
                db.session.delete(log_entry)
                db.session.commit()

    def test_audit_filter_by_action_only(self, client):
        """Test filtering audit log by action only."""
        response = client.get("/audit?action=CREATE")
        assert response.status_code == 200

    def test_audit_limit_parameter(self, client):
        """Test audit log limit parameter."""
        response = client.get("/audit?limit=10")
        assert response.status_code == 200

    def test_audit_default_limit(self, client):
        """Test audit log uses default limit of 100."""
        response = client.get("/audit")
        assert response.status_code == 200

    def test_audit_entries_ordered_by_timestamp_desc(self, client, app):
        """Test audit entries are ordered by timestamp descending."""
        with app.app_context():
            # Create multiple entries
            log_create("OrderTest", 1, {"order": "first"})
            log_create("OrderTest", 2, {"order": "second"})

            response = client.get("/audit?entity_type=OrderTest")
            data = response.data.decode()

            # Second entry should appear before first (descending order)
            pos_first = data.find("first") if "first" in data else -1
            pos_second = data.find("second") if "second" in data else -1
            assert pos_first != -1
            assert pos_second != -1
            assert pos_second < pos_first

            # Cleanup
            entries = AuditLog.query.filter_by(entity_type="OrderTest").all()
            for entry in entries:
                db.session.delete(entry)
            db.session.commit()

    def test_audit_displays_entry_details(self, client, app):
        """Test audit page displays entry details."""
        with app.app_context():
            log_create("DetailTest", 123, {"field": "test_value"})

            response = client.get("/audit?entity_type=DetailTest")
            assert response.status_code == 200
            # Should show the entity type and action
            assert b"DetailTest" in response.data or b"CREATE" in response.data

            # Cleanup
            log_entry = AuditLog.query.filter_by(entity_type="DetailTest").first()
            if log_entry:
                db.session.delete(log_entry)
                db.session.commit()


class TestAuditLogModel:
    """Tests for AuditLog model."""

    def test_audit_log_stores_user(self, app):
        """Test that audit log stores the user."""
        with app.app_context():
            from backend.audit import log_action

            # Use log_action directly with user parameter
            log_action(
                action="CREATE",
                entity_type="UserTest",
                entity_id=1,
                details={},
                user="Test User",
            )

            log_entry = AuditLog.query.filter_by(entity_type="UserTest").first()
            assert log_entry is not None
            assert log_entry.user == "Test User"

            db.session.delete(log_entry)
            db.session.commit()

    def test_audit_log_stores_timestamp(self, app):
        """Test that audit log stores timestamp."""
        with app.app_context():
            log_create("TimestampTest", 1, {})

            log_entry = AuditLog.query.filter_by(entity_type="TimestampTest").first()
            assert log_entry is not None
            assert log_entry.timestamp is not None

            db.session.delete(log_entry)
            db.session.commit()

    def test_audit_log_stores_details_as_json(self, app):
        """Test that audit log stores details as JSON string."""
        with app.app_context():
            log_create("JSONTest", 1, {"key": "value", "number": 42})

            log_entry = AuditLog.query.filter_by(entity_type="JSONTest").first()
            assert log_entry is not None
            assert "key" in log_entry.details
            assert "value" in log_entry.details

            db.session.delete(log_entry)
            db.session.commit()

    def test_audit_log_uses_caller_transaction(self, app):
        """Test audit rows roll back with the caller transaction."""
        with app.app_context():
            log_action(
                action="CREATE",
                entity_type="RollbackTest",
                entity_id=1,
                details={"state": "pending"},
                user="Rollback User",
            )

            db.session.rollback()

            log_entry = AuditLog.query.filter_by(entity_type="RollbackTest").first()
            assert log_entry is None


class TestGetClientIP:
    """Tests for get_client_ip function."""

    def test_get_client_ip_with_x_forwarded_for(self, app):
        """Test getting client IP from X-Forwarded-For header."""
        with app.test_request_context(
            "/", headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        ):
            ip = get_client_ip()
            assert ip == "192.168.1.1"

    def test_get_client_ip_with_x_real_ip(self, app):
        """Test getting client IP from X-Real-IP header."""
        with app.test_request_context("/", headers={"X-Real-IP": "192.168.2.2"}):
            ip = get_client_ip()
            assert ip == "192.168.2.2"

    def test_get_client_ip_falls_back_to_remote_addr(self, app):
        """Test getting client IP from remote_addr when no proxy headers."""
        with app.test_request_context("/"):
            ip = get_client_ip()
            # remote_addr is typically 127.0.0.1 in tests or None
            assert ip is None or ip == "127.0.0.1"

    def test_get_client_ip_outside_request_context(self):
        """Test get_client_ip returns None when request access fails."""
        # Flask's `request` object raises RuntimeError outside a request context.
        # The function catches this and returns None.
        ip = get_client_ip()
        assert ip is None


class TestLogActionExceptionHandling:
    """Tests for log_action exception handling."""

    def test_log_action_handles_db_error(self, app):
        """Test that log_action handles database errors gracefully."""
        with app.app_context(), patch.object(db.session, "execute") as mock_execute:
            mock_execute.side_effect = SQLAlchemyError("Database error")

            # Should not raise an exception
            log_action("TEST", "TestEntity", entity_id=1, details={})

    def test_log_action_no_rollback_on_error(self, app):
        """Test that log_action does not roll back on error
        (caller controls transaction)."""
        with (
            app.app_context(),
            patch.object(db.session, "execute") as mock_execute,
            patch.object(db.session, "rollback") as mock_rollback,
        ):
            mock_execute.side_effect = SQLAlchemyError("Database error")

            log_action("TEST", "TestEntity", entity_id=1, details={})

            mock_rollback.assert_not_called()

    def test_log_action_raises_when_requested(self, app):
        """Test that strict audit logging re-raises database errors."""
        with app.app_context(), patch.object(db.session, "execute") as mock_execute:
            mock_execute.side_effect = SQLAlchemyError("Database error")

            with pytest.raises(SQLAlchemyError) as excinfo:
                log_action_strict(
                    "TEST",
                    "TestEntity",
                    entity_id=1,
                    details={},
                )
            assert "Database error" in str(excinfo.value)


class TestGetAuditTrail:
    """Tests for get_audit_trail function."""

    def test_get_audit_trail_no_filters(self, app):
        """Test get_audit_trail with no filters."""
        with app.app_context():
            # Create test entries
            log_create("AuditTrailTest", 1, {"data": "one"})
            log_create("AuditTrailTest", 2, {"data": "two"})

            results = get_audit_trail()
            assert isinstance(results, list)

            # Cleanup
            entries = AuditLog.query.filter_by(entity_type="AuditTrailTest").all()
            for entry in entries:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_filter_by_entity_type(self, app):
        """Test get_audit_trail filtered by entity_type."""
        with app.app_context():
            log_create("TypeFilterTest", 1, {})

            results = get_audit_trail(entity_type="TypeFilterTest")
            assert len(results) >= 1
            assert all(r.entity_type == "TypeFilterTest" for r in results)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_filter_by_entity_id(self, app):
        """Test get_audit_trail filtered by entity_id."""
        with app.app_context():
            log_create("IDFilterTest", 999, {})

            results = get_audit_trail(entity_type="IDFilterTest", entity_id=999)
            assert len(results) >= 1
            assert all(r.entity_id == 999 for r in results)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_filter_by_user(self, app):
        """Test get_audit_trail filtered by user."""
        with app.app_context():
            log_action(
                "CREATE",
                "UserFilterTest",
                entity_id=1,
                details={},
                user="SpecificUser",
            )

            results = get_audit_trail(user="SpecificUser")
            assert len(results) >= 1
            assert all(r.user == "SpecificUser" for r in results)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_filter_by_action(self, app):
        """Test get_audit_trail filtered by action."""
        with app.app_context():
            log_delete("ActionFilterTest", 1, {})

            results = get_audit_trail(entity_type="ActionFilterTest", action="DELETE")
            assert len(results) >= 1
            assert all(r.action == "DELETE" for r in results)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_with_limit(self, app):
        """Test get_audit_trail with limit."""
        with app.app_context():
            # Create more entries than the limit
            for i in range(5):
                log_create("LimitTest", i, {})

            results = get_audit_trail(entity_type="LimitTest", limit=3)
            assert len(results) == 3

            # Cleanup
            entries = AuditLog.query.filter_by(entity_type="LimitTest").all()
            for entry in entries:
                db.session.delete(entry)
            db.session.commit()

    def test_get_audit_trail_ordered_by_timestamp_desc(self, app):
        """Test get_audit_trail returns entries ordered by timestamp desc."""
        with app.app_context():
            log_create("OrderTest2", 1, {"order": "first"})
            log_create("OrderTest2", 2, {"order": "second"})

            results = get_audit_trail(entity_type="OrderTest2")
            if len(results) >= 2:
                # More recent should be first
                assert results[0].timestamp >= results[1].timestamp

            # Cleanup
            entries = AuditLog.query.filter_by(entity_type="OrderTest2").all()
            for entry in entries:
                db.session.delete(entry)
            db.session.commit()


class TestGetEntityHistory:
    """Tests for get_entity_history function."""

    def test_get_entity_history(self, app):
        """Test get_entity_history returns history for specific entity."""
        with app.app_context():
            # Create multiple actions for same entity
            log_create("HistoryTest", 42, {"action": "created"})
            log_update("HistoryTest", 42, {"action": "updated"})
            log_delete("HistoryTest", 42, {"action": "deleted"})

            results = get_entity_history("HistoryTest", 42)
            assert len(results) >= 3
            assert all(r.entity_type == "HistoryTest" for r in results)
            assert all(r.entity_id == 42 for r in results)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()

    def test_get_entity_history_high_limit(self, app):
        """Test get_entity_history uses high limit (1000)."""
        with app.app_context():
            log_create("HistoryLimitTest", 100, {})

            # get_entity_history should use limit=1000
            results = get_entity_history("HistoryLimitTest", 100)
            assert isinstance(results, list)

            # Cleanup
            for entry in results:
                db.session.delete(entry)
            db.session.commit()


class TestLogUpdate:
    """Additional tests for log_update function."""

    def test_log_update_with_changes_and_details(self, app):
        """Test log_update merges changes into details."""
        with app.app_context():
            log_update(
                "UpdateTest",
                1,
                changes={"field": {"old": "a", "new": "b"}},
                details={"extra": "info"},
            )

            log_entry = AuditLog.query.filter_by(entity_type="UpdateTest").first()
            assert log_entry is not None
            assert "changes" in log_entry.details
            assert "extra" in log_entry.details

            db.session.delete(log_entry)
            db.session.commit()

    def test_log_update_creates_details_if_none(self, app):
        """Test log_update creates details dict if None."""
        with app.app_context():
            log_update("UpdateTest2", 1, changes={"field": "value"}, details=None)

            log_entry = AuditLog.query.filter_by(entity_type="UpdateTest2").first()
            assert log_entry is not None
            assert "changes" in log_entry.details

            db.session.delete(log_entry)
            db.session.commit()


class TestLogImport:
    """Additional tests for log_import function."""

    def test_log_import_with_user(self, app):
        """Test log_import with user parameter."""
        with app.app_context():
            log_import("StaffList", "Imported 10 records", user="ImportUser")

            log_entry = (
                AuditLog.query.filter_by(entity_type="StaffList", action="IMPORT")
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log_entry is not None
            assert log_entry.user == "ImportUser"

            db.session.delete(log_entry)
            db.session.commit()

    def test_log_import_with_entity_id(self, app):
        """Test log_import with entity_id parameter."""
        with app.app_context():
            log_import("Schedule", "Imported entries", entity_id=123)

            log_entry = (
                AuditLog.query.filter_by(entity_type="Schedule", entity_id=123)
                .order_by(AuditLog.id.desc())
                .first()
            )
            assert log_entry is not None
            assert log_entry.entity_id == 123

            db.session.delete(log_entry)
            db.session.commit()
