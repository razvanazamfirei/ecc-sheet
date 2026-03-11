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
        seconds=env_int("PERMANENT_SESSION_LIFETIME") or 2_678_400
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
    DEFAULT_CUTOFF_HOUR: ClassVar[int] = env_int("DEFAULT_CUTOFF_HOUR") or 17
    DEFAULT_CUTOFF_MINUTE: ClassVar[int] = env_int("DEFAULT_CUTOFF_MINUTE") or 30
    TIMEZONE: ClassVar[str] = env_str("TIMEZONE") or "America/New_York"
    DAY_RESET_HOUR: ClassVar[int] = env_int("DAY_RESET_HOUR") or 8  # Day resets at 8 AM

    # Role-specific cutoff times (can be customized per role)
    # Format: (hour, minute) for 17:30 cutoff
    ROLE_CUTOFF_HOURS: ClassVar[dict[str, int]] = {
        "ECA 1": 17,
        "ECA 2": 17,
        "ECC 1": 17,
        "ECC 2": 17,
        "ECC 3": 17,
        "ECC 4": 17,
        "ECC 5": 17,
        "PPMC": 17,
        "Late Late 1": 17,
        "Late Late 2": 17,
        "EP/HUP 13": 17,
        "H12": 17,
        "H13": 17,
        "H14": 17,
        "HUP EP 12": 17,
    }

    ROLE_CUTOFF_MINUTES: ClassVar[dict[str, int]] = {
        "ECA 1": 30,
        "ECA 2": 30,
        "ECC 1": 30,
        "ECC 2": 30,
        "ECC 3": 30,
        "ECC 4": 30,
        "ECC 5": 30,
        "PPMC": 30,
        "Late Late 1": 30,
        "Late Late 2": 30,
        "EP/HUP 13": 30,
        "H12": 30,
        "H13": 30,
        "H14": 30,
        "HUP EP 12": 30,
    }
