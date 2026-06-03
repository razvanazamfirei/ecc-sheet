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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import timedelta
from pathlib import Path
from typing import Any, overload
from urllib.parse import urlsplit

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


def _env_str_preserve_blank(name: str, default: str) -> str:
    """Return a trimmed env string while preserving explicit blank values."""
    if name not in os.environ:
        return default
    return str(os.getenv(name, "")).strip()


def _csv_values(value: object, default: str | Sequence[str] = "") -> list[str]:
    """Return strings from a CSV string or sequence-like config value."""
    if value is None:
        value = default
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, Sequence):
        items = value
    else:
        items = (str(value),)
    return [str(item).strip() for item in items if str(item).strip()]


def env_csv(name: str, default: str = "") -> list[str]:
    """Return a comma-separated environment variable as trimmed values."""
    return _csv_values(os.getenv(name, default))


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_DOTENV_PATH = _PROJECT_ROOT / ".env"
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

SAML_SESSION_USER_KEY = "auth_user"
SAML_SESSION_DATA_KEY = "saml_authn"
SAML_LOGIN_REQUEST_ID_KEY = "saml_request_id"
SAML_LOGOUT_REQUEST_ID_KEY = "saml_logout_request_id"
SAML_REQUEST_TYPE_TO_KEY = {
    "login": SAML_LOGIN_REQUEST_ID_KEY,
    "logout": SAML_LOGOUT_REQUEST_ID_KEY,
}
SAML_PUBLIC_ENDPOINTS = frozenset(
    {"auth.login", "auth.acs", "auth.sls", "auth.logout", "auth.metadata"}
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
    ADMIN_USERS: list[str]
    FIRST_CALL_ROLES: list[str]
    PAYROLL_ADMIN_USERS: list[str]
    MOCK_USERS_ENABLED: bool
    REPORT_VIEW_ALL_USERS: list[str]
    SAML_ENABLED: bool
    SAML_SETTINGS_PATH: str | None
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
            USER_NAME=_env_str_preserve_blank("USER_NAME", "Admin"),
            AUTH_PROXY_USERNAME_HEADER=env_str("AUTH_PROXY_USERNAME_HEADER", ""),
            ADMIN_USERS=env_csv("ADMIN_USERS", "Admin"),
            FIRST_CALL_ROLES=env_csv("FIRST_CALL_ROLES", "First Call"),
            PAYROLL_ADMIN_USERS=env_csv("PAYROLL_ADMIN_USERS"),
            MOCK_USERS_ENABLED=env_flag("MOCK_USERS_ENABLED"),
            REPORT_VIEW_ALL_USERS=env_csv("REPORT_VIEW_ALL_USERS"),
            SAML_ENABLED=env_flag("SAML_ENABLED"),
            SAML_SETTINGS_PATH=env_str("SAML_SETTINGS_PATH"),
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


@dataclass(frozen=True)
class AuthSettings:
    """Runtime authentication settings parsed from Flask config."""

    user_name: str
    proxy_username_header: str
    admin_users: list[str]
    first_call_roles: list[str]
    payroll_admin_users: list[str]
    mock_users_enabled: bool
    report_view_all_users: list[str]

    @classmethod
    def from_env(cls) -> AuthSettings:
        return cls(
            user_name=_env_str_preserve_blank("USER_NAME", "Admin"),
            proxy_username_header=env_str("AUTH_PROXY_USERNAME_HEADER", ""),
            admin_users=env_csv("ADMIN_USERS", "Admin"),
            first_call_roles=env_csv("FIRST_CALL_ROLES", "First Call"),
            payroll_admin_users=env_csv("PAYROLL_ADMIN_USERS"),
            mock_users_enabled=env_flag("MOCK_USERS_ENABLED"),
            report_view_all_users=env_csv("REPORT_VIEW_ALL_USERS"),
        )

    @classmethod
    def from_mapping(cls, config: Mapping[str, object]) -> AuthSettings:
        return cls(
            user_name=_config_str(config, "USER_NAME", "Admin"),
            proxy_username_header=_config_str(config, "AUTH_PROXY_USERNAME_HEADER", ""),
            admin_users=_config_csv(config, "ADMIN_USERS", "Admin"),
            first_call_roles=_config_csv(config, "FIRST_CALL_ROLES", "First Call"),
            payroll_admin_users=_config_csv(config, "PAYROLL_ADMIN_USERS"),
            mock_users_enabled=_config_bool(config, "MOCK_USERS_ENABLED"),
            report_view_all_users=_config_csv(config, "REPORT_VIEW_ALL_USERS"),
        )


def _config_str(
    config: Mapping[str, object],
    key: str,
    default: str,
) -> str:
    value = config.get(key, default)
    if value is None:
        return default
    return str(value).strip()


def _config_bool(
    config: Mapping[str, object],
    key: str,
    *,
    default: bool = False,
) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in _TRUTHY_ENV_VALUES


def _config_csv(
    config: Mapping[str, object],
    key: str,
    default: str | Sequence[str] = "",
) -> list[str]:
    return _csv_values(config.get(key), default)


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


def get_auth_settings(config: Mapping[str, object] | None = None) -> AuthSettings:
    """Return auth settings from a mapping or from the loaded environment config."""
    if config is None:
        return AuthSettings.from_env()
    return AuthSettings.from_mapping(config)


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


def load_saml_settings(  # noqa: PLR0912
    config: Mapping[str, object] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """Load the configured OneLogin toolkit settings from app config."""
    from backend.errors import (  # noqa: PLC0415
        SAMLInvalidJSONError,
        SAMLInvalidSettingsError,
        SAMLSettingsNotFoundError,
    )

    if config is None:
        config = _SETTINGS.to_flask_config()

    settings_path_value = config.get("SAML_SETTINGS_PATH")

    if not settings_path_value:
        raise SAMLSettingsNotFoundError(
            "SAML is enabled but no SAML settings were configured. "
            "Set SAML_SETTINGS_PATH."
        )

    path = Path(str(settings_path_value))
    if not path.is_absolute():
        path = (_PROJECT_ROOT / path).resolve()
    if not path.is_file():
        raise SAMLSettingsNotFoundError(f"SAML settings file not found: {path}")

    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SAMLInvalidJSONError(
            f"SAML settings file is not valid JSON: {path}"
        ) from exc

    if not isinstance(settings, dict):
        raise SAMLInvalidSettingsError(
            f"SAML settings file must contain a JSON object: {path}"
        )
    base_path = str(path.parent)

    idp = settings.get("idp")
    if isinstance(idp, dict):
        single_logout = idp.get("singleLogoutService")
        if single_logout is None:
            single_logout = {}
            idp["singleLogoutService"] = single_logout

        if isinstance(single_logout, dict):
            single_sign_on = idp.get("singleSignOnService", {})
            sso_url = (
                str(single_sign_on.get("url") or "").strip()
                if isinstance(single_sign_on, dict)
                else ""
            )
            parsed_sso_url = urlsplit(sso_url)
            sso_path_parts = [part for part in parsed_sso_url.path.split("/") if part]

            if (
                parsed_sso_url.scheme in {"http", "https"}
                and parsed_sso_url.netloc
                and len(sso_path_parts) == 2
                and sso_path_parts[0] == "samlp"
            ):
                single_logout["url"] = parsed_sso_url._replace(
                    path=f"/samlp/{sso_path_parts[1]}/logout",
                    query="",
                    fragment="",
                ).geturl()
            else:
                logout_url = str(single_logout.get("url") or "").strip()
                parsed_logout_url = urlsplit(logout_url)
                if (
                    logout_url
                    and parsed_logout_url.scheme in {"http", "https"}
                    and parsed_logout_url.netloc
                ):
                    single_logout["url"] = logout_url
                else:
                    single_logout.pop("url", None)

    return settings, base_path


Config = _SETTINGS
