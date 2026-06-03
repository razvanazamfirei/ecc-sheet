import os
from dataclasses import dataclass, fields
from datetime import timedelta
from pathlib import Path

from dotenv import dotenv_values

from backend.env_utils import env_csv, env_flag, env_int, env_str

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
    def from_env(cls) -> "Settings":
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


def get_settings() -> Settings:
    return _SETTINGS


Config = _SETTINGS
