"""Tests for configuration module."""

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import reload
from types import ModuleType

import pytest

import backend.config

_CONFIG_ENV_KEYS = (
    "SECRET_KEY",
    "DATABASE_URL",
    "FLASK_ENV",
    "USER_NAME",
    "AUTH_PROXY_USERNAME_HEADER",
    "ADMIN_USERS",
    "FIRST_CALL_ROLES",
    "PAYROLL_ADMIN_USERS",
    "MOCK_USERS_ENABLED",
    "REPORT_VIEW_ALL_USERS",
    "SAML_ENABLED",
    "SAML_SETTINGS_PATH",
    "SAML_USERNAME_ATTRIBUTES",
    "SAML_USE_NAME_ID",
    "SAML_DEFAULT_NEXT_URL",
    "RESEND_API_KEY",
    "DEFAULT_SENDER_EMAIL",
    "SESSION_COOKIE_SECURE",
    "SESSION_COOKIE_HTTPONLY",
    "SESSION_COOKIE_SAMESITE",
    "PERMANENT_SESSION_LIFETIME",
    "CSP_POLICY",
    "AMION_BASE_URL",
    "AMION_SCHEDULE_CODE",
    "ANESTHESIA_SQL_CONNECTION_STRING",
    "ANESTHESIA_SQL_SOURCE_TABLE",
    "ANESTHESIA_SQL_PROVIDER_TYPE",
    "ANESTHESIA_SQL_TIMEOUT",
    "ANESTHESIA_FETCHER_ENABLED",
    "ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS",
    "ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS",
    "PAYROLL_PROGRAM",
    "PAYROLL_COMPANY",
    "PAYROLL_BATCH",
    "PAYROLL_PAY_CODE",
    "PAYROLL_DEPT",
    "PAYROLL_EXPENSE",
    "PAYROLL_ACCT_UNIT",
    "PAYROLL_LABEL_SUFFIX",
    "TIMEZONE",
    "DAY_RESET_HOUR",
)


@contextmanager
def _config_env(
    monkeypatch: pytest.MonkeyPatch,
    **values: str,
) -> Iterator[ModuleType]:
    with monkeypatch.context() as env:
        for key in _CONFIG_ENV_KEYS:
            env.delenv(key, raising=False)
        for key, value in values.items():
            env.setenv(key, value)

        yield reload(backend.config)

    reload(backend.config)


class TestConfig:
    """Tests for Config class."""

    def test_secret_key_from_env(self, monkeypatch):
        """Test SECRET_KEY is read from environment."""
        expected_value = "test-secret-key-from-env"
        with _config_env(monkeypatch, SECRET_KEY=expected_value) as config:
            assert expected_value == config.Config.SECRET_KEY

    def test_secret_key_default(self):
        """Test SECRET_KEY has a default value when not in environment."""
        assert backend.config.Config.SECRET_KEY is not None
        assert len(backend.config.Config.SECRET_KEY) > 0

    def test_database_uri_from_env(self, monkeypatch):
        """Test DATABASE_URL is read from environment."""
        with _config_env(monkeypatch, DATABASE_URL="sqlite:///test.db") as config:
            assert config.Config.SQLALCHEMY_DATABASE_URI == "sqlite:///test.db"

    def test_database_uri_default(self, monkeypatch):
        """Test DATABASE_URL has a default value."""
        with _config_env(monkeypatch) as config:
            assert "sqlite" in config.Config.SQLALCHEMY_DATABASE_URI

    def test_user_name_from_env(self, monkeypatch):
        """Test USER_NAME is read from environment."""
        with _config_env(monkeypatch, USER_NAME="Test User") as config:
            assert config.Config.USER_NAME == "Test User"

    def test_user_name_default(self, monkeypatch):
        """Test USER_NAME defaults to Admin."""
        with _config_env(monkeypatch) as config:
            assert config.Config.USER_NAME == "Admin"

    def test_auth_proxy_username_header_from_env(self, monkeypatch):
        """Test AUTH_PROXY_USERNAME_HEADER is read from environment."""
        with _config_env(
            monkeypatch, AUTH_PROXY_USERNAME_HEADER="X-Auth-User"
        ) as config:
            assert config.Config.AUTH_PROXY_USERNAME_HEADER == "X-Auth-User"

    def test_auth_allowlists_from_env(self, monkeypatch):
        """Test auth allowlists and mock-user flag are read through config."""
        with _config_env(
            monkeypatch,
            ADMIN_USERS="Admin, Test Admin",
            FIRST_CALL_ROLES="First Call, Backup Call",
            PAYROLL_ADMIN_USERS="Payroll User",
            MOCK_USERS_ENABLED="true",
            REPORT_VIEW_ALL_USERS="Viewer, *",
        ) as config:
            assert config.Config.ADMIN_USERS == ["Admin", "Test Admin"]
            assert config.Config.FIRST_CALL_ROLES == ["First Call", "Backup Call"]
            assert config.Config.PAYROLL_ADMIN_USERS == ["Payroll User"]
            assert config.Config.MOCK_USERS_ENABLED is True
            assert config.Config.REPORT_VIEW_ALL_USERS == ["Viewer", "*"]

    def test_config_is_settings_singleton(self):
        """Test Config is the Settings singleton returned by get_settings()."""
        settings = backend.config.get_settings()
        assert backend.config.Config is settings
        assert (
            settings.SQLALCHEMY_DATABASE_URI
            == backend.config.Config.SQLALCHEMY_DATABASE_URI
        )
        assert settings.to_flask_config()["FLASK_ENV"] == settings.FLASK_ENV

    def test_saml_config_from_env(self, monkeypatch):
        """Test first-party SAML settings are read from the environment."""
        with _config_env(
            monkeypatch,
            SAML_ENABLED="true",
            SAML_SETTINGS_PATH="instance/saml/settings.json",
            SAML_USERNAME_ATTRIBUTES="name,email",
            SAML_USE_NAME_ID="false",
            SAML_DEFAULT_NEXT_URL="/reports",
        ) as config:
            assert config.Config.SAML_ENABLED is True
            assert config.Config.SAML_SETTINGS_PATH == "instance/saml/settings.json"
            assert config.Config.SAML_USERNAME_ATTRIBUTES == ["name", "email"]
            assert config.Config.SAML_USE_NAME_ID is False
            assert config.Config.SAML_DEFAULT_NEXT_URL == "/reports"

    def test_amion_base_url_defaults_to_https(self, monkeypatch):
        """Test Amion integration defaults to HTTPS."""
        with _config_env(monkeypatch) as config:
            assert config.Config.AMION_BASE_URL.startswith("https://")

    def test_session_cookie_security_from_env(self, monkeypatch):
        """Test session security settings are read from environment."""
        with _config_env(
            monkeypatch,
            FLASK_ENV="production",
            SESSION_COOKIE_SECURE="true",
            SESSION_COOKIE_HTTPONLY="false",
            SESSION_COOKIE_SAMESITE="Strict",
            PERMANENT_SESSION_LIFETIME="3600",
            CSP_POLICY="default-src 'self'",
        ) as config:
            assert config.Config.SESSION_COOKIE_SECURE is True
            assert config.Config.SESSION_COOKIE_HTTPONLY is False
            assert config.Config.SESSION_COOKIE_SAMESITE == "Strict"
            assert int(config.Config.PERMANENT_SESSION_LIFETIME.total_seconds()) == 3600
            assert config.Config.CSP_POLICY == "default-src 'self'"

    def test_session_cookie_secure_defaults_true_in_production(self, monkeypatch):
        """Test secure cookies default on in production."""
        with _config_env(monkeypatch, FLASK_ENV="production") as config:
            assert config.Config.SESSION_COOKIE_SECURE is True

    def test_timezone_default(self, monkeypatch):
        """Test TIMEZONE defaults to America/New_York."""
        with _config_env(monkeypatch) as config:
            assert config.Config.TIMEZONE == "America/New_York"

    def test_day_reset_hour_default(self, monkeypatch):
        """Test DAY_RESET_HOUR defaults to 8."""
        with _config_env(monkeypatch) as config:
            assert config.Config.DAY_RESET_HOUR == 8

    def test_zero_value_time_config_from_env(self, monkeypatch):
        """Test explicit zero values are preserved for time-related settings."""
        with _config_env(monkeypatch, DAY_RESET_HOUR="0", TIMEZONE="UTC") as config:
            assert config.Config.DAY_RESET_HOUR == 0
            assert config.Config.TIMEZONE == "UTC"

    def test_sqlalchemy_track_modifications_disabled(self):
        """Test SQLALCHEMY_TRACK_MODIFICATIONS is disabled."""
        assert backend.config.Config.SQLALCHEMY_TRACK_MODIFICATIONS is False

    def test_anesthesia_fetcher_settings_from_env(self, monkeypatch):
        """Test fetcher configuration is read from environment."""
        with _config_env(
            monkeypatch,
            ANESTHESIA_FETCHER_ENABLED="true",
            ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS="120",
            ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS="2",
        ) as config:
            assert config.Config.ANESTHESIA_FETCHER_ENABLED is True
            assert config.Config.ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS == 120
            assert config.Config.ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS == 2
