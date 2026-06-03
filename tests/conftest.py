"""
Pytest fixtures and configuration for test suite
"""

import os
import pathlib
import tempfile
from collections.abc import Iterator
from datetime import time

import pytest
from flask import Flask
from flask.testing import FlaskClient, FlaskCliRunner
from sqlalchemy.orm import Session

# Set the test database URL before importing the Flask app so that Config
# reads the test URI at module-import time (backend.app calls db.init_app
# during import, which reads DATABASE_URL from the environment).
_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(prefix="ecc-sheet-tests-", suffix=".db")
os.close(_TEST_DB_FD)
_TEST_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
_TEST_ENV = pytest.MonkeyPatch()
_TEST_ENV.setenv("DATABASE_URL", _TEST_DATABASE_URL)
_TEST_ENV.setenv("USER_NAME", "Admin")
_TEST_ENV.setenv("ADMIN_USERS", "CI-Test-User,Admin,Test User")
# Ensure app import does not require optional SAML dependencies.
# Individual tests opt-in via the saml_enabled_app fixture.
_TEST_ENV.setenv("SAML_ENABLED", "false")


from backend.app import app as flask_app
from backend.app import init_db
from backend.models import DailySheet, Resident, Role, TimeEntry, db
from backend.utils import get_effective_date


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    """Create application for testing"""
    flask_app.config.update(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": _TEST_DATABASE_URL,
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for testing
            "SECRET_KEY": "test-secret-key",
            "AUTH_PROXY_USERNAME_HEADER": "",
            "SAML_ENABLED": False,  # Tests opt in via saml_enabled_app fixture
        }
    )

    # db.init_app(app) ran at module import time with the production URI.
    # Remove the extension registration so we can re-initialize with the
    # temp test database URI. init_app disposes old engines internally.
    flask_app.extensions.pop("sqlalchemy", None)
    db.init_app(flask_app)

    with flask_app.app_context():
        db.drop_all()
        init_db()

    yield flask_app

    # Cleanup - properly dispose database connections
    with flask_app.app_context():
        db.session.remove()
        db.engine.dispose()

    pathlib.Path(_TEST_DB_PATH).unlink(missing_ok=True)
    _TEST_ENV.undo()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create test client"""
    return app.test_client()


@pytest.fixture
def saml_enabled_app(app: Flask, monkeypatch):
    """Enable SAML for the duration of a test and restore the original value."""
    monkeypatch.delenv("MOCK_USERS_ENABLED", raising=False)
    original = app.config["SAML_ENABLED"]
    app.config["SAML_ENABLED"] = True
    yield app
    app.config["SAML_ENABLED"] = original


@pytest.fixture
def runner(app: Flask) -> FlaskCliRunner:
    """Create CLI test runner"""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app: Flask) -> Iterator[Session]:
    """Create a database session for testing"""
    with app.app_context():
        yield db.session
        db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_resident(app: Flask) -> Iterator[Resident]:
    """Create a sample resident for testing"""
    with app.app_context():
        # Check if resident already exists
        resident = Resident.query.filter_by(name="Test Resident").first()
        if resident is None:
            resident = Resident(name="Test Resident", active=True)
            db.session.add(resident)
            db.session.commit()
        assert resident is not None

        yield resident

        # Clean up
        try:
            db.session.delete(resident)
            db.session.commit()
        except Exception:
            db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_role(app: Flask) -> Iterator[Role]:
    """Create a sample role for testing"""
    with app.app_context():
        # Check if role already exists
        role = Role.query.filter_by(name="Test Role").first()
        if role is None:
            role = Role(
                name="Test Role", cutoff_hour=17, cutoff_minute=30, display_order=99
            )
            db.session.add(role)
            db.session.commit()
        assert role is not None

        yield role

        # Clean up
        try:
            db.session.delete(role)
            db.session.commit()
        except Exception:
            db.session.rollback()


# noinspection PyBroadException
@pytest.fixture
def sample_time_entry(
    app: Flask, sample_resident: Resident, sample_role: Role
) -> Iterator[TimeEntry]:
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
def sample_daily_sheet(app: Flask) -> Iterator[DailySheet]:
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
def clean_database(app: Flask) -> Iterator[None]:
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
