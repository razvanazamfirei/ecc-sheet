"""Shared staff/person field normalization for import and matching workflows."""

from __future__ import annotations

from dataclasses import dataclass, field

CLASS_YEAR_ALIASES: dict[str, str] = {
    "ca1": "CA-1",
    "ca-1": "CA-1",
    "ca2": "CA-2",
    "ca-2": "CA-2",
    "ca3": "CA-3",
    "ca-3": "CA-3",
    "fellow": "Fellow",
    "omfs": "OMFS",
}


@dataclass(frozen=True, slots=True)
class StaffFields:
    """Normalize the reusable staff fields that come from external sources."""

    class_year_aliases: dict[str, str] = field(
        default_factory=lambda: dict(CLASS_YEAR_ALIASES)
    )

    @staticmethod
    def clean_text(value: str | None) -> str:
        """Return a trimmed string, defaulting missing values to empty."""
        return value.strip() if value else ""

    def split_name(self, name: str) -> tuple[str | None, str | None]:
        """Split a full name into first and last components."""
        cleaned = self.clean_text(name)
        if not cleaned:
            return None, None
        if "," in cleaned:
            last_name, first_name = (part.strip() for part in cleaned.split(",", 1))
            return first_name or None, last_name or None
        parts = cleaned.rsplit(" ", 1)
        if not parts or not parts[0]:
            return None, None
        first_name = parts[0].strip() or None
        last_name = parts[1].strip() if len(parts) > 1 else None
        return first_name, last_name or None

    def class_year(self, value: str) -> str | None:
        """Return a normalized class-year alias, preserving unknown values."""
        if not (normalized := self.clean_text(value)):
            return None
        return self.class_year_aliases.get(normalized.casefold(), normalized)

    @staticmethod
    def normalized_name(raw_name: str) -> str:
        """Normalize whitespace and case in a person name for matching."""
        return " ".join(raw_name.split()).casefold()

    def name_match_keys(self, raw_name: str) -> set[str]:
        """Return common first/last and last/comma/first match keys for a name."""
        normalized = self.normalized_name(raw_name)
        if not normalized:
            return set()

        keys = {normalized}
        if "," in normalized:
            last_name, remainder = (part.strip() for part in normalized.split(",", 1))
            first_tokens = remainder.split()
            if first_tokens:
                first_name = first_tokens[0]
                keys.add(f"{last_name}, {first_name}")
                keys.add(f"{first_name} {last_name}")
            return keys

        name_parts = normalized.split()
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = name_parts[-1]
            keys.add(f"{first_name} {last_name}")
            keys.add(f"{last_name}, {first_name}")
        return keys


staff_fields = StaffFields()
