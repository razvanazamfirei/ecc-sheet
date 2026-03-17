import os
from datetime import timedelta
from pathlib import Path
from typing import ClassVar

from dotenv import dotenv_values

from .env_utils import env_csv, env_flag, env_int, env_str

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


def _env_int_default(name: str, default: int) -> int:
    """Return an env int while preserving literal zero values."""
    value = env_int(name)
    return default if value is None else value


def _env_str_default(name: str, default: str) -> str:
    """Return an env string or a default when the value is blank/unset."""
    value = env_str(name)
    return default if value is None else value


class Config:
    SECRET_KEY: ClassVar[str] = env_str("SECRET_KEY") or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI: ClassVar[str] = (
        env_str("DATABASE_URL") or "sqlite:///ecc_sheet.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: ClassVar[bool] = False
    FLASK_ENV: ClassVar[str] = (env_str("FLASK_ENV") or "development").lower()
    USER_NAME: ClassVar[str] = env_str("USER_NAME") or "Admin"
    AUTH_PROXY_USERNAME_HEADER: ClassVar[str] = (
        env_str("AUTH_PROXY_USERNAME_HEADER") or ""
    )
    SAML_ENABLED: ClassVar[bool] = env_flag("SAML_ENABLED")
    SAML_SETTINGS_PATH: ClassVar[str | None] = env_str("SAML_SETTINGS_PATH")
    SAML_SETTINGS_JSON: ClassVar[str | None] = env_str("SAML_SETTINGS_JSON")
    SAML_USERNAME_ATTRIBUTES: ClassVar[list[str]] = env_csv(
        "SAML_USERNAME_ATTRIBUTES",
        (
            "name,"
            "email,"
            "uid,"
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name,"
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress,"
            "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"
        ),
    )
    SAML_USE_NAME_ID: ClassVar[bool] = env_flag("SAML_USE_NAME_ID", default=True)
    SAML_DEFAULT_NEXT_URL: ClassVar[str] = env_str("SAML_DEFAULT_NEXT_URL") or "/"

    # Resend
    RESEND_API_KEY: ClassVar[str | None] = env_str("RESEND_API_KEY")
    DEFAULT_SENDER_EMAIL: ClassVar[str] = (
        env_str("DEFAULT_SENDER_EMAIL") or "onboarding@resend.dev"
    )

    # Session / browser security
    SESSION_COOKIE_SECURE: ClassVar[bool] = env_flag(
        "SESSION_COOKIE_SECURE", default=(FLASK_ENV == "production")
    )
    SESSION_COOKIE_HTTPONLY: ClassVar[bool] = env_flag(
        "SESSION_COOKIE_HTTPONLY", default=True
    )
    SESSION_COOKIE_SAMESITE: ClassVar[str | None] = _same_site_env(
        "SESSION_COOKIE_SAMESITE", default="Lax"
    )
    PERMANENT_SESSION_LIFETIME: ClassVar[timedelta] = timedelta(
        seconds=_env_int_default("PERMANENT_SESSION_LIFETIME", 2_678_400)
    )
    CSP_POLICY: ClassVar[str | None] = env_str("CSP_POLICY")

    # Amion integration
    AMION_BASE_URL: ClassVar[str] = (
        env_str("AMION_BASE_URL") or "https://www.amion.com/cgi-bin/ocs"
    )
    AMION_SCHEDULE_CODE: ClassVar[str] = env_str("AMION_SCHEDULE_CODE") or "upennane"

    # Anesthesia stop-time sync
    ANESTHESIA_SQL_CONNECTION_STRING: ClassVar[str | None] = env_str(
        "ANESTHESIA_SQL_CONNECTION_STRING"
    )
    ANESTHESIA_SQL_SOURCE_TABLE: ClassVar[str | None] = env_str(
        "ANESTHESIA_SQL_SOURCE_TABLE"
    )
    ANESTHESIA_SQL_PROVIDER_TYPE: ClassVar[str] = (
        env_str("ANESTHESIA_SQL_PROVIDER_TYPE") or "Anes Resident"
    )
    ANESTHESIA_SQL_TIMEOUT: ClassVar[int] = _env_int_default(
        "ANESTHESIA_SQL_TIMEOUT", 30
    )
    ANESTHESIA_FETCHER_ENABLED: ClassVar[bool] = env_flag(
        "ANESTHESIA_FETCHER_ENABLED", default=False
    )
    ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS: ClassVar[int] = _env_int_default(
        "ANESTHESIA_AUTO_SYNC_INTERVAL_SECONDS", 120
    )
    ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS: ClassVar[int] = _env_int_default(
        "ANESTHESIA_AUTO_SYNC_LOOKBACK_DAYS", 1
    )

    # Payroll export defaults (used to seed the DB on first run via PayrollSettings)
    PAYROLL_PROGRAM: ClassVar[str | None] = env_str("PAYROLL_PROGRAM")
    PAYROLL_COMPANY: ClassVar[str | None] = env_str("PAYROLL_COMPANY")
    PAYROLL_BATCH: ClassVar[int | None] = env_int("PAYROLL_BATCH")
    PAYROLL_PAY_CODE: ClassVar[int | None] = env_int("PAYROLL_PAY_CODE")
    PAYROLL_DEPT: ClassVar[int | None] = env_int("PAYROLL_DEPT")
    PAYROLL_EXPENSE: ClassVar[int | None] = env_int("PAYROLL_EXPENSE")
    PAYROLL_ACCT_UNIT: ClassVar[int | None] = env_int("PAYROLL_ACCT_UNIT")
    PAYROLL_LABEL_SUFFIX: ClassVar[str | None] = env_str("PAYROLL_LABEL_SUFFIX")

    # Time tracking configuration
    TIMEZONE: ClassVar[str] = _env_str_default("TIMEZONE", "America/New_York")
    DAY_RESET_HOUR: ClassVar[int] = _env_int_default(
        "DAY_RESET_HOUR", 8
    )  # Day resets at 8 AM
