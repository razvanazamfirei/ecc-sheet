"""
Pytest fixtures and configuration for test suite
"""

import os
import pathlib
import tempfile
from datetime import date, time

import pytest

from backend.app import app as flask_app
from backend.app import init_db
from backend.models import DailySheet, Resident, Role, TimeEntry, db


@pytest.fixture(scope="session")
def app():
    """Create application for testing"""
    # Create a temporary database
    db_fd, db_path = tempfile.mkstemp()

    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for testing
            "SECRET_KEY": "test-secret-key",
        }
    )

    with flask_app.app_context():
        init_db()

    yield flask_app

    # Cleanup
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
        except:
            db.session.rollback()


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
        except:
            db.session.rollback()


@pytest.fixture
def sample_time_entry(app, sample_resident, sample_role):
    """Create a sample time entry for testing"""
    with app.app_context():
        entry = TimeEntry(
            date=date.today(),
            resident_id=sample_resident.id,
            role_id=sample_role.id,
            exit_time=time(20, 0),  # 20:00
            airway_assist=False,
            emergency=False,
            dinner_break=False,
            paper_record=False,
        )
        db.session.add(entry)
        db.session.commit()

        yield entry

        # Clean up
        try:
            db.session.delete(entry)
            db.session.commit()
        except:
            db.session.rollback()


@pytest.fixture
def sample_daily_sheet(app):
    """Create a sample daily sheet for testing"""
    with app.app_context():
        # Check if sheet already exists for today
        sheet = DailySheet.query.filter_by(date=date.today()).first()
        if not sheet:
            sheet = DailySheet(date=date.today(), locked=False, submitted=False)
            db.session.add(sheet)
            db.session.commit()

        yield sheet

        # Clean up
        try:
            db.session.delete(sheet)
            db.session.commit()
        except:
            db.session.rollback()


@pytest.fixture
def clean_database(app):
    """Clean database before and after test"""
    with app.app_context():
        # Clean before test
        TimeEntry.query.delete()
        DailySheet.query.filter(
            DailySheet.id.notin_(
                db.session.query(DailySheet.id).filter_by(date=date.today())
            )
        ).delete(synchronize_session=False)
        db.session.commit()

        yield

        # Clean after test
        TimeEntry.query.delete()
        db.session.commit()
