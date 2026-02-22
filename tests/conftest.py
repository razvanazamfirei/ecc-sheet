"""
Pytest fixtures and configuration for test suite
"""

import os
import pathlib
import tempfile
from datetime import time

import pytest

from backend.app import app as flask_app
from backend.app import init_db
from backend.models import DailySheet, Resident, Role, TimeEntry, db
from backend.utils import get_effective_date


@pytest.fixture(scope="session")
def app():
    """Create application for testing"""
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp()

    # Set environment variables for admin access in tests
    os.environ["ADMIN_USERS"] = "CI-Test-User,Admin,Test User"

    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for testing
            "SECRET_KEY": "test-secret-key",
        }
    )

    # db.init_app(app) ran at module import time with the production URI.
    # Remove the extension registration so we can re-initialize with the
    # temp test database URI. init_app disposes old engines internally.
    flask_app.extensions.pop("sqlalchemy", None)
    db.init_app(flask_app)

    with flask_app.app_context():
        init_db()

    yield flask_app

    # Cleanup - properly dispose database connections
    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()

    os.close(db_fd)
    pathlib.Path(db_path).unlink()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI test runner"""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create a database session for testing"""
    with app.app_context():
        yield db.session
        db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_resident(app):
    """Create a sample resident for testing"""
    with app.app_context():
        # Check if resident already exists
        resident = Resident.query.filter_by(name="Test Resident").first()
        if not resident:
            resident = Resident(name="Test Resident", active=True)
            db.session.add(resident)
            db.session.commit()

        yield resident

        # Clean up
        try:
            db.session.delete(resident)
            db.session.commit()
        except Exception:
            db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_role(app):
    """Create a sample role for testing"""
    with app.app_context():
        # Check if role already exists
        role = Role.query.filter_by(name="Test Role").first()
        if not role:
            role = Role(
                name="Test Role", cutoff_hour=17, cutoff_minute=30, display_order=99
            )
            db.session.add(role)
            db.session.commit()

        yield role

        # Clean up
        try:
            db.session.delete(role)
            db.session.commit()
        except Exception:
            db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_time_entry(app, sample_resident, sample_role):
    """Create a sample time entry for testing"""
    with app.app_context():
        entry = TimeEntry(
            date=get_effective_date(),
            resident_id=sample_resident.id,
            role_id=sample_role.id,
            exit_time=time(20, 0),  # 20:00
        )
        db.session.add(entry)
        db.session.commit()

        yield entry

        # Clean up
        try:
            db.session.delete(entry)
            db.session.commit()
        except Exception:
            db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_daily_sheet(app):
    """Create a sample daily sheet for testing"""
    with app.app_context():
        today = get_effective_date()
        sheet = DailySheet.query.filter_by(date=today).first()
        if not sheet:
            sheet = DailySheet(date=today, locked=False, submitted=False)
            db.session.add(sheet)
            db.session.commit()

        yield sheet

        # Clean up
        try:
            db.session.delete(sheet)
            db.session.commit()
        except Exception:
            db.session.rollback()


@pytest.fixture
def clean_database(app):
    """Clean database before and after test"""
    with app.app_context():
        today = get_effective_date()

        # Clean before test
        TimeEntry.query.delete(synchronize_session="fetch")
        DailySheet.query.filter(
            DailySheet.id.notin_(db.session.query(DailySheet.id).filter_by(date=today))
        ).delete(synchronize_session="fetch")

        # Unlock today's sheet if it exists
        today_sheet = DailySheet.query.filter_by(date=today).first()
        if today_sheet:
            today_sheet.locked = False

        db.session.commit()

        yield

        # Clean after test
        TimeEntry.query.delete(synchronize_session="fetch")
        db.session.commit()
