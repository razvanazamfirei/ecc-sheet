"""Tests for audit functionality."""

from datetime import date

import pytest

from backend.audit import log_create, log_delete, log_import, log_lock, log_update
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

            log = AuditLog.query.filter_by(action="LOCK").order_by(
                AuditLog.id.desc()
            ).first()
            assert log is not None
            assert "2024-01-15" in log.details

            db.session.delete(log)
            db.session.commit()

    def test_log_unlock(self, app):
        """Test logging an unlock action."""
        with app.app_context():
            log_lock("2024-01-15", locked=False)

            log = AuditLog.query.filter_by(action="UNLOCK").order_by(
                AuditLog.id.desc()
            ).first()
            assert log is not None

            db.session.delete(log)
            db.session.commit()

    def test_log_import(self, app):
        """Test logging an import action."""
        with app.app_context():
            log_import("Schedule", "Imported 5 entries for 2024-01-15")

            log = AuditLog.query.filter_by(action="IMPORT").order_by(
                AuditLog.id.desc()
            ).first()
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
