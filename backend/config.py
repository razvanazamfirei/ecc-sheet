import os
from datetime import timedelta
from typing import ClassVar

from dotenv import load_dotenv

from .env_utils import env_flag, env_int, env_str

load_dotenv()


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
