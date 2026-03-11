"""Helpers for normalized environment variable parsing."""

from __future__ import annotations

import os

_TRUTHY_ENV_VALUES = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, *, default: bool = False) -> bool:
    """Return an environment flag normalized to a boolean."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in _TRUTHY_ENV_VALUES


def env_int(name: str) -> int | None:
    """Return an integer environment variable or None when blank/invalid."""
    value = env_str(name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def env_str(name: str) -> str | None:
    """Return a trimmed environment variable or None when blank/unset."""
    value = os.getenv(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def env_csv(name: str, default: str = "") -> list[str]:
    """Return a comma-separated environment variable as trimmed values."""
    return [
        item.strip() for item in os.getenv(name, default).split(",") if item.strip()
    ]
