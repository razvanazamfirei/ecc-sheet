import copy
import json
from pathlib import Path
from typing import Any

# Load settings from the generated instance_settings.json file
CONFIG_PATH = Path(__file__).parent / "instance_settings.json"

try:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        _settings: dict[str, Any] = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    raise RuntimeError(
        f"Failed to load required instance settings from {CONFIG_PATH}. "
        f"This file must exist and contain valid JSON. "
        f"Error details: {e}"
    ) from e

DEFAULT_CUTOFF_HOUR: int = _settings.get("default_cutoff_hour", 17)
DEFAULT_CUTOFF_MINUTE: int = _settings.get("default_cutoff_minute", 30)

# Build role lookup tables and lists based on JSON
ROLES: list[dict[str, Any]] = _settings.get("roles", [])

# Provide lists and dictionaries for usage in code
DEFAULT_ROLES = [
    (r["name"], r.get("display_order", i + 1)) for i, r in enumerate(ROLES)
]

BACKUP_ROLE_NAMES = frozenset([r["name"] for r in ROLES if r.get("is_backup")])
CALL_TEAM_ROLE_NAMES = frozenset([r["name"] for r in ROLES if r.get("is_call_team")])

# Cutoff overrides for specific roles
ROLE_CUTOFF_HOURS = {r["name"]: r["cutoff_hour"] for r in ROLES if "cutoff_hour" in r}
ROLE_CUTOFF_MINUTES = {
    r["name"]: r["cutoff_minute"] for r in ROLES if "cutoff_minute" in r
}

LATE_ROLE_NAMES = frozenset([r["name"] for r in ROLES if r.get("is_late_role")])
WEEKDAY_BACKUP_ROLE_NAMES = frozenset(
    [r["name"] for r in ROLES if r.get("is_weekday_backup")]
)
SCHEDULE_ROLE_NAMES = frozenset(
    [r["name"] for r in ROLES if r.get("is_schedule_importable")]
)


def get_role_definitions():
    """Returns the full parsed role configuration JSON."""
    return copy.deepcopy(ROLES)
