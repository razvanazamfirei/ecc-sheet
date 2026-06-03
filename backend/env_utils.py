"""Helpers for normalized environment variable parsing."""

from __future__ import annotations

import os
from typing import overload

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
