"""Configuration loading for ECC Sheet.

This module owns the two runtime configuration sources:

1. Environment variables, optionally seeded from the project `.env` file, are
   parsed into the immutable `Settings` object used by Flask.
2. `backend/instance_settings.json` is parsed into `InstanceSettings` for role
   definitions, default cutoffs, and role classification flags.

Use `get_flask_config()` when configuring the Flask app so environment and
instance settings are merged consistently.
"""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, fields
from datetime import timedelta
from pathlib import Path
from typing import Any, overload

from dotenv import dotenv_values

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, *, default: bool = False) -> bool:
    """Return an environment flag normalized to a boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY_ENV_VALUES


@overload
def env_int(name: str) -> int | None: ...


@overload
def env_int(name: str, default: int) -> int: ...


def env_int(name: str, default: int | None = None) -> int | None:
    """Return an integer environment variable or None when blank/invalid."""
    value = env_str(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@overload
def env_str(name: str) -> str | None: ...


@overload
def env_str(name: str, default: str) -> str: ...


def env_str(name: str, default: str | None = None) -> str | None:
    """Return a trimmed environment variable or None when blank/unset."""
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def env_csv(name: str, default: str = "") -> list[str]:
    """Return a comma-separated environment variable as trimmed values."""
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]


_PROJECT_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _PROJECT_DOTENV_PATH.is_file():
    for _key, _value in dotenv_values(_PROJECT_DOTENV_PATH, interpolate=False).items():
        if _value is not None:
            os.environ.setdefault(_key, _value)


def _same_site_env(name: str, *, default: str | None = "Lax") -> str | None:
    """Parse Flask's session same-site cookie policy."""
    v = env_str(name)
    if v is None:
        return default

    normalized = v.lower()
    if normalized == "lax":
        return "Lax"
    if normalized == "strict":
        return "Strict"
    if normalized == "none":
        return "None"
    return default


_DEFAULT_SAML_USERNAME_ATTRIBUTES = (
    "Identity,"
    "name,"
    "email,"
    "uid,"
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name,"
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress,"
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"
)


INSTANCE_SETTINGS_PATH = Path(__file__).parent / "instance_settings.json"


def _load_instance_settings_json(
    config_path: Path = INSTANCE_SETTINGS_PATH,
) -> dict[str, Any]:
    """Load the checked-in instance settings JSON."""
    try:
        with config_path.open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to load required instance settings from {config_path}. "
            f"This file must exist and contain valid JSON. "
            f"Error details: {exc}"
        ) from exc


@dataclass(frozen=True)
class InstanceSettings:
    """Parsed role and cutoff settings from `instance_settings.json`."""

    default_cutoff_hour: int
    default_cutoff_minute: int
    roles: tuple[dict[str, Any], ...]

    @classmethod
    def from_mapping(cls, settings: Mapping[str, Any]) -> InstanceSettings:
        roles = settings.get("roles", [])
        if not isinstance(roles, list):
            roles = []
        return cls(
            default_cutoff_hour=int(settings.get("default_cutoff_hour", 17)),
            default_cutoff_minute=int(settings.get("default_cutoff_minute", 30)),
            roles=tuple(copy.deepcopy(roles)),
        )

    @property
    def default_roles(self) -> list[tuple[str, int]]:
        """Return role names paired with configured display order."""
        return [
            (role["name"], role.get("display_order", index + 1))
            for index, role in enumerate(self.roles)
        ]

    @property
    def backup_role_names(self) -> frozenset[str]:
        """Return role names classified as backup roles."""
        return frozenset(role["name"] for role in self.roles if role.get("is_backup"))

    @property
    def call_team_role_names(self) -> frozenset[str]:
        """Return role names classified as call-team roles."""
        return frozenset(
            role["name"] for role in self.roles if role.get("is_call_team")
        )

    @property
    def role_cutoff_hours(self) -> dict[str, int]:
        """Return per-role cutoff-hour overrides."""
        return {
            role["name"]: role["cutoff_hour"]
            for role in self.roles
            if "cutoff_hour" in role
        }

    @property
    def role_cutoff_minutes(self) -> dict[str, int]:
        """Return per-role cutoff-minute overrides."""
        return {
            role["name"]: role["cutoff_minute"]
            for role in self.roles
            if "cutoff_minute" in role
        }

    @property
    def late_role_names(self) -> frozenset[str]:
        """Return role names classified as late roles."""
        return frozenset(
            role["name"] for role in self.roles if role.get("is_late_role")
        )

    @property
    def weekday_backup_role_names(self) -> frozenset[str]:
        """Return role names classified as weekday backup roles."""
        return frozenset(
            role["name"] for role in self.roles if role.get("is_weekday_backup")
        )

    @property
    def schedule_role_names(self) -> frozenset[str]:
        """Return role names that can be imported from the schedule."""
        return frozenset(
            role["name"] for role in self.roles if role.get("is_schedule_importable")
        )

    def get_role_definitions(self) -> list[dict[str, Any]]:
        """Return deep copies of the configured role definitions."""
        return copy.deepcopy(list(self.roles))

    def to_flask_config(self) -> dict[str, object]:
        """Return instance settings in Flask config key format."""
        return {
            "INSTANCE_SETTINGS_PATH": str(INSTANCE_SETTINGS_PATH),
            "DEFAULT_CUTOFF_HOUR": self.default_cutoff_hour,
            "DEFAULT_CUTOFF_MINUTE": self.default_cutoff_minute,
            "DEFAULT_ROLES": self.default_roles,
            "BACKUP_ROLE_NAMES": self.backup_role_names,
            "CALL_TEAM_ROLE_NAMES": self.call_team_role_names,
            "ROLE_CUTOFF_HOURS": self.role_cutoff_hours,
            "ROLE_CUTOFF_MINUTES": self.role_cutoff_minutes,
            "LATE_ROLE_NAMES": self.late_role_names,
            "WEEKDAY_BACKUP_ROLE_NAMES": self.weekday_backup_role_names,
            "SCHEDULE_ROLE_NAMES": self.schedule_role_names,
        }


@dataclass(frozen=True)
class Settings:
    SECRET_KEY: str
    SQLALCHEMY_DATABASE_URI: str
    SQLALCHEMY_TRACK_MODIFICATIONS: bool
    FLASK_ENV: str
    USER_NAME: str
    AUTH_PROXY_USERNAME_HEADER: str
    SAML_ENABLED: bool
    SAML_SETTINGS_PATH: str | None
    SAML_SETTINGS_JSON: str | None
    SAML_USERNAME_ATTRIBUTES: list[str]
    SAML_USE_NAME_ID: bool
    SAML_DEFAULT_NEXT_URL: str
    RESEND_API_KEY: str | None
    DEFAULT_SENDER_EMAIL: str
    SESSION_COOKIE_SECURE: bool
    SESSION_COOKIE_HTTPONLY: bool
    SESSION_COOKIE_SAMESITE: str | None
    PERMANENT_SESSION_LIFETIME: timedelta
    CSP_POLICY: str | None
    AMION_BASE_URL: str
    AMION_SCHEDULE_CODE: str
    ANESTHESIA_SQL_CONNECTION_STRING: str | None
    ANESTHESIA_SQL_SOURCE_TABLE: str | None
    ANESTHESIA_SQL_PROVIDER_TYPE: str
    ANESTHESIA_SQL_TIMEOUT: int
    ANESTHESIA_FETCHER_ENABLED: bool
    ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS: int
    ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS: int
    PAYROLL_PROGRAM: str | None
    PAYROLL_COMPANY: str | None
    PAYROLL_BATCH: int | None
    PAYROLL_PAY_CODE: int | None
    PAYROLL_DEPT: int | None
    PAYROLL_EXPENSE: int | None
    PAYROLL_ACCT_UNIT: int | None
    PAYROLL_LABEL_SUFFIX: str | None
    TIMEZONE: str
    DAY_RESET_HOUR: int

    @classmethod
    def from_env(cls) -> Settings:
        flask_env = env_str("FLASK_ENV", "development").lower()
        return cls(
            SECRET_KEY=env_str("SECRET_KEY") or os.urandom(32).hex(),
            SQLALCHEMY_DATABASE_URI=env_str("DATABASE_URL", "sqlite:///ecc_sheet.db"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            FLASK_ENV=flask_env,
            USER_NAME=env_str("USER_NAME", "Admin"),
            AUTH_PROXY_USERNAME_HEADER=env_str("AUTH_PROXY_USERNAME_HEADER", ""),
            SAML_ENABLED=env_flag("SAML_ENABLED"),
            SAML_SETTINGS_PATH=env_str("SAML_SETTINGS_PATH"),
            SAML_SETTINGS_JSON=env_str("SAML_SETTINGS_JSON"),
            SAML_USERNAME_ATTRIBUTES=env_csv(
                "SAML_USERNAME_ATTRIBUTES",
                _DEFAULT_SAML_USERNAME_ATTRIBUTES,
            ),
            SAML_USE_NAME_ID=env_flag("SAML_USE_NAME_ID", default=True),
            SAML_DEFAULT_NEXT_URL=env_str("SAML_DEFAULT_NEXT_URL", "/"),
            RESEND_API_KEY=env_str("RESEND_API_KEY"),
            DEFAULT_SENDER_EMAIL=env_str(
                "DEFAULT_SENDER_EMAIL", "onboarding@resend.dev"
            ),
            SESSION_COOKIE_SECURE=env_flag(
                "SESSION_COOKIE_SECURE", default=(flask_env == "production")
            ),
            SESSION_COOKIE_HTTPONLY=env_flag("SESSION_COOKIE_HTTPONLY", default=True),
            SESSION_COOKIE_SAMESITE=_same_site_env(
                "SESSION_COOKIE_SAMESITE", default="Lax"
            ),
            PERMANENT_SESSION_LIFETIME=timedelta(
                seconds=env_int("PERMANENT_SESSION_LIFETIME", 2_678_400)
            ),
            CSP_POLICY=env_str("CSP_POLICY"),
            AMION_BASE_URL=env_str(
                "AMION_BASE_URL", "https://www.amion.com/cgi-bin/ocs"
            ),
            AMION_SCHEDULE_CODE=env_str("AMION_SCHEDULE_CODE", "upennane"),
            ANESTHESIA_SQL_CONNECTION_STRING=env_str(
                "ANESTHESIA_SQL_CONNECTION_STRING"
            ),
            ANESTHESIA_SQL_SOURCE_TABLE=env_str("ANESTHESIA_SQL_SOURCE_TABLE"),
            ANESTHESIA_SQL_PROVIDER_TYPE=env_str(
                "ANESTHESIA_SQL_PROVIDER_TYPE", "Anes Resident"
            ),
            ANESTHESIA_SQL_TIMEOUT=env_int("ANESTHESIA_SQL_TIMEOUT", 30),
            ANESTHESIA_FETCHER_ENABLED=env_flag(
                "ANESTHESIA_FETCHER_ENABLED", default=False
            ),
            ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS=env_int(
                "ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS", 120
            ),
            ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS=env_int(
                "ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS", 1
            ),
            PAYROLL_PROGRAM=env_str("PAYROLL_PROGRAM"),
            PAYROLL_COMPANY=env_str("PAYROLL_COMPANY"),
            PAYROLL_BATCH=env_int("PAYROLL_BATCH"),
            PAYROLL_PAY_CODE=env_int("PAYROLL_PAY_CODE"),
            PAYROLL_DEPT=env_int("PAYROLL_DEPT"),
            PAYROLL_EXPENSE=env_int("PAYROLL_EXPENSE"),
            PAYROLL_ACCT_UNIT=env_int("PAYROLL_ACCT_UNIT"),
            PAYROLL_LABEL_SUFFIX=env_str("PAYROLL_LABEL_SUFFIX"),
            TIMEZONE=env_str("TIMEZONE", "America/New_York"),
            DAY_RESET_HOUR=env_int("DAY_RESET_HOUR", 8),
        )

    def to_flask_config(self) -> dict[str, object]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


_SETTINGS = Settings.from_env()
_INSTANCE_SETTINGS = InstanceSettings.from_mapping(_load_instance_settings_json())

DEFAULT_CUTOFF_HOUR: int = _INSTANCE_SETTINGS.default_cutoff_hour
DEFAULT_CUTOFF_MINUTE: int = _INSTANCE_SETTINGS.default_cutoff_minute
ROLES: list[dict[str, Any]] = _INSTANCE_SETTINGS.get_role_definitions()
DEFAULT_ROLES: list[tuple[str, int]] = _INSTANCE_SETTINGS.default_roles
BACKUP_ROLE_NAMES: frozenset[str] = _INSTANCE_SETTINGS.backup_role_names
CALL_TEAM_ROLE_NAMES: frozenset[str] = _INSTANCE_SETTINGS.call_team_role_names
ROLE_CUTOFF_HOURS: dict[str, int] = _INSTANCE_SETTINGS.role_cutoff_hours
ROLE_CUTOFF_MINUTES: dict[str, int] = _INSTANCE_SETTINGS.role_cutoff_minutes
LATE_ROLE_NAMES: frozenset[str] = _INSTANCE_SETTINGS.late_role_names
WEEKDAY_BACKUP_ROLE_NAMES: frozenset[str] = _INSTANCE_SETTINGS.weekday_backup_role_names
SCHEDULE_ROLE_NAMES: frozenset[str] = _INSTANCE_SETTINGS.schedule_role_names


def get_settings() -> Settings:
    return _SETTINGS


def get_instance_settings() -> InstanceSettings:
    """Return parsed instance settings."""
    return _INSTANCE_SETTINGS


def get_role_definitions() -> list[dict[str, Any]]:
    """Return deep copies of the configured role definitions."""
    return _INSTANCE_SETTINGS.get_role_definitions()


def get_flask_config() -> dict[str, object]:
    """Return the merged Flask config from env and instance settings."""
    config = _SETTINGS.to_flask_config()
    config.update(_INSTANCE_SETTINGS.to_flask_config())
    return config


Config = _SETTINGS
