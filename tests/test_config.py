"""Tests for configuration module."""

import os
from importlib import reload
from unittest.mock import patch

import backend.config


class TestConfig:
    """Tests for Config class."""

    def test_secret_key_from_env(self):
        """Test SECRET_KEY is read from environment."""
        expected_value = os.urandom(16).hex()
        with patch.dict(os.environ, {"SECRET_KEY": expected_value}):
            reload(backend.config)
            assert expected_value == backend.config.Config.SECRET_KEY

    def test_secret_key_default(self):
        """Test SECRET_KEY has a default value when not in environment."""
        # This test verifies the default in the code, not runtime behavior
        # since .env file may override the default during load_dotenv()
        # The Config class should have SECRET_KEY defined
        assert backend.config.Config.SECRET_KEY is not None
        assert len(backend.config.Config.SECRET_KEY) > 0

    def test_database_uri_from_env(self):
        """Test DATABASE_URL is read from environment."""
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///test.db"}):
            reload(backend.config)
            assert backend.config.Config.SQLALCHEMY_DATABASE_URI == "sqlite:///test.db"

    def test_database_uri_default(self):
        """Test DATABASE_URL has a default value."""
        env = os.environ.copy()
        env.pop("DATABASE_URL", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert "sqlite" in backend.config.Config.SQLALCHEMY_DATABASE_URI

    def test_user_name_from_env(self):
        """Test USER_NAME is read from environment."""
        with patch.dict(os.environ, {"USER_NAME": "Test User"}):
            reload(backend.config)
            assert backend.config.Config.USER_NAME == "Test User"

    def test_user_name_default(self):
        """Test USER_NAME defaults to Admin."""
        env = os.environ.copy()
        env.pop("USER_NAME", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.USER_NAME == "Admin"

    def test_email_host_default(self):
        """Test EMAIL_HOST has default value."""
        assert backend.config.Config.EMAIL_HOST == "smtp.gmail.com"

    def test_email_port_from_env(self):
        """Test EMAIL_PORT is read from environment."""
        with patch.dict(os.environ, {"EMAIL_PORT": "465"}):
            reload(backend.config)
            assert backend.config.Config.EMAIL_PORT == 465

    def test_email_port_default(self):
        """Test EMAIL_PORT defaults to 587."""
        env = os.environ.copy()
        env.pop("EMAIL_PORT", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.EMAIL_PORT == 587

    def test_auth_proxy_username_header_from_env(self):
        """Test AUTH_PROXY_USERNAME_HEADER is read from environment."""
        with patch.dict(os.environ, {"AUTH_PROXY_USERNAME_HEADER": "X-Auth-User"}):
            reload(backend.config)
            assert backend.config.Config.AUTH_PROXY_USERNAME_HEADER == "X-Auth-User"

    def test_amion_base_url_defaults_to_https(self):
        """Test Amion integration defaults to HTTPS."""
        env = os.environ.copy()
        env.pop("AMION_BASE_URL", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.AMION_BASE_URL.startswith("https://")

    def test_session_cookie_security_from_env(self):
        """Test session security settings are read from environment."""
        with patch.dict(
            os.environ,
            {
                "FLASK_ENV": "production",
                "SESSION_COOKIE_SECURE": "true",
                "SESSION_COOKIE_HTTPONLY": "false",
                "SESSION_COOKIE_SAMESITE": "Strict",
                "PERMANENT_SESSION_LIFETIME": "3600",
                "CSP_POLICY": "default-src 'self'",
            },
            clear=True,
        ):
            reload(backend.config)
            assert backend.config.Config.SESSION_COOKIE_SECURE is True
            assert backend.config.Config.SESSION_COOKIE_HTTPONLY is False
            assert backend.config.Config.SESSION_COOKIE_SAMESITE == "Strict"
            assert (
                int(backend.config.Config.PERMANENT_SESSION_LIFETIME.total_seconds())
                == 3600
            )
            assert backend.config.Config.CSP_POLICY == "default-src 'self'"

    def test_session_cookie_secure_defaults_true_in_production(self):
        """Test secure cookies default on in production."""
        env = os.environ.copy()
        env["FLASK_ENV"] = "production"
        env.pop("SESSION_COOKIE_SECURE", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.SESSION_COOKIE_SECURE is True

    def test_timezone_default(self):
        """Test TIMEZONE defaults to America/New_York."""
        env = os.environ.copy()
        env.pop("TIMEZONE", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.TIMEZONE == "America/New_York"

    def test_day_reset_hour_default(self):
        """Test DAY_RESET_HOUR defaults to 8."""
        env = os.environ.copy()
        env.pop("DAY_RESET_HOUR", None)

        with patch.dict(os.environ, env, clear=True):
            reload(backend.config)
            assert backend.config.Config.DAY_RESET_HOUR == 8

    def test_default_cutoff_hour(self):
        """Test DEFAULT_CUTOFF_HOUR from environment."""
        with patch.dict(os.environ, {"DEFAULT_CUTOFF_HOUR": "18"}):
            reload(backend.config)
            assert backend.config.Config.DEFAULT_CUTOFF_HOUR == 18

    def test_default_cutoff_minute(self):
        """Test DEFAULT_CUTOFF_MINUTE from environment."""
        with patch.dict(os.environ, {"DEFAULT_CUTOFF_MINUTE": "45"}):
            reload(backend.config)
            assert backend.config.Config.DEFAULT_CUTOFF_MINUTE == 45

    def test_role_cutoff_hours_contains_common_roles(self):
        """Test ROLE_CUTOFF_HOURS contains expected roles."""
        assert "ECC 1" in backend.config.Config.ROLE_CUTOFF_HOURS
        assert "ECA 1" in backend.config.Config.ROLE_CUTOFF_HOURS
        assert "PPMC" in backend.config.Config.ROLE_CUTOFF_HOURS

    def test_role_cutoff_minutes_contains_common_roles(self):
        """Test ROLE_CUTOFF_MINUTES contains expected roles."""
        assert "ECC 1" in backend.config.Config.ROLE_CUTOFF_MINUTES
        assert "ECA 1" in backend.config.Config.ROLE_CUTOFF_MINUTES
        assert "PPMC" in backend.config.Config.ROLE_CUTOFF_MINUTES

    def test_sqlalchemy_track_modifications_disabled(self):
        """Test SQLALCHEMY_TRACK_MODIFICATIONS is disabled."""
        assert backend.config.Config.SQLALCHEMY_TRACK_MODIFICATIONS is False
