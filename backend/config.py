import os
from datetime import timedelta
from typing import ClassVar

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str) -> int | None:
    """Parse an integer environment variable; return None if unset or non-numeric."""
    v = os.getenv(name)
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _bool_env(name: str, *, default: bool = False) -> bool:
    """Parse a boolean environment variable."""
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _str_env(name: str) -> str | None:
    """Return a trimmed environment variable or None when blank/unset."""
    v = os.getenv(name)
    if v is None:
        return None
    stripped = v.strip()
    return stripped or None


def _same_site_env(name: str, *, default: str | None = "Lax") -> str | None:
    """Parse Flask's session same-site cookie policy."""
    v = _str_env(name)
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
    SECRET_KEY: ClassVar[str] = _str_env("SECRET_KEY") or os.urandom(32).hex()
    SQLALCHEMY_DATABASE_URI: ClassVar[str] = os.getenv(
        "DATABASE_URL", "sqlite:///ecc_sheet.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: ClassVar[bool] = False
    FLASK_ENV: ClassVar[str] = os.getenv("FLASK_ENV", "development").strip().lower()
    USER_NAME: ClassVar[str] = os.getenv("USER_NAME", "Admin")
    AUTH_PROXY_USERNAME_HEADER: ClassVar[str] = os.getenv(
        "AUTH_PROXY_USERNAME_HEADER", ""
    ).strip()

    # Session / browser security
    SESSION_COOKIE_SECURE: ClassVar[bool] = _bool_env(
        "SESSION_COOKIE_SECURE", default=(FLASK_ENV == "production")
    )
    SESSION_COOKIE_HTTPONLY: ClassVar[bool] = _bool_env(
        "SESSION_COOKIE_HTTPONLY", default=True
    )
    SESSION_COOKIE_SAMESITE: ClassVar[str | None] = _same_site_env(
        "SESSION_COOKIE_SAMESITE", default="Lax"
    )
    PERMANENT_SESSION_LIFETIME: ClassVar[timedelta] = timedelta(
        seconds=_int_env("PERMANENT_SESSION_LIFETIME") or 2_678_400
    )
    CSP_POLICY: ClassVar[str | None] = _str_env("CSP_POLICY")

    # Email configuration
    EMAIL_HOST: ClassVar[str] = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT: ClassVar[int] = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USERNAME: ClassVar[str | None] = os.getenv("EMAIL_USERNAME")
    EMAIL_PASSWORD: ClassVar[str | None] = os.getenv("EMAIL_PASSWORD")
    EMAIL_RECIPIENT: ClassVar[str | None] = os.getenv("EMAIL_RECIPIENT")

    # Amion integration
    AMION_BASE_URL: ClassVar[str] = os.getenv(
        "AMION_BASE_URL", "https://www.amion.com/cgi-bin/ocs"
    ).strip()
    AMION_SCHEDULE_CODE: ClassVar[str] = os.getenv("AMION_SCHEDULE_CODE", "upennane")

    # Payroll export defaults (used to seed the DB on first run via PayrollSettings)
    PAYROLL_PROGRAM: ClassVar[str | None] = os.getenv("PAYROLL_PROGRAM")
    PAYROLL_COMPANY: ClassVar[str | None] = os.getenv("PAYROLL_COMPANY")
    PAYROLL_BATCH: ClassVar[int | None] = _int_env("PAYROLL_BATCH")
    PAYROLL_PAY_CODE: ClassVar[int | None] = _int_env("PAYROLL_PAY_CODE")
    PAYROLL_DEPT: ClassVar[int | None] = _int_env("PAYROLL_DEPT")
    PAYROLL_EXPENSE: ClassVar[int | None] = _int_env("PAYROLL_EXPENSE")
    PAYROLL_ACCT_UNIT: ClassVar[int | None] = _int_env("PAYROLL_ACCT_UNIT")
    PAYROLL_LABEL_SUFFIX: ClassVar[str | None] = os.getenv("PAYROLL_LABEL_SUFFIX")

    # Time tracking configuration
    DEFAULT_CUTOFF_HOUR: ClassVar[int] = int(os.getenv("DEFAULT_CUTOFF_HOUR", "17"))
    DEFAULT_CUTOFF_MINUTE: ClassVar[int] = int(os.getenv("DEFAULT_CUTOFF_MINUTE", "30"))
    TIMEZONE: ClassVar[str] = os.getenv(
        "TIMEZONE", "America/New_York"
    )  # Philadelphia time
    DAY_RESET_HOUR: ClassVar[int] = int(
        os.getenv("DAY_RESET_HOUR", "8")
    )  # Day resets at 8 AM

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
