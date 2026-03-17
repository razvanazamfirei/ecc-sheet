"""Resident bootstrap/import from a managed CSV file."""

from __future__ import annotations

import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any

from email_validator import EmailNotValidError

from .audit import log_create, log_import, log_update
from .db_session import commit_or_rollback
from .errors import ConflictError, ValidationError
from .models import Resident, db
from .parsing import parse_iso_date
from .payroll_audit import (
    filter_payroll_resident_changes,
    payroll_resident_details,
)
from .resident_normalization import (
    CLASS_YEAR_ALIASES,
    canonicalize_class_year,
    clean_text,
    normalize_email,
    split_name,
)

logger = logging.getLogger(__name__)

_HEADER_ALIASES: dict[str, str] = {
    "abbreviation": "abbreviation",
    "active": "active",
    "backup_id": "backup_id",
    "class_year": "class_year",
    "email": "email",
    "epic_id": "epic_id",
    "epicid": "epic_id",
    "first_name": "first_name",
    "hire_date": "hire_date",
    "last_name": "last_name",
    "lawson_id": "lawson_id",
    "name": "name",
    "phone": "phone",
    "resident_name": "name",
}
_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "n", "off"})


@dataclass(frozen=True, slots=True)
class ResidentCsvRecord:
    """Normalized resident data parsed from one CSV row."""

    row_number: int
    name: str
    first_name: str | None
    last_name: str | None
    epic_id: str | None
    class_year: str | None
    email: str | None
    phone: str | None
    abbreviation: str | None
    backup_id: str | None
    lawson_id: int | None
    hire_date: date | None
    active: bool | None


@dataclass(frozen=True, slots=True)
class ResidentCsvImportResult:
    """Summary of a resident CSV import run."""

    total_records: int
    created: int
    updated: int
    skipped: int
    dry_run: bool

    def summary(self) -> str:
        """Return a compact human-readable summary."""
        action = "Would create" if self.dry_run else "Created"
        update_action = "would update" if self.dry_run else "updated"
        return (
            f"Processed {self.total_records} resident records; "
            f"{action.lower()} {self.created}; {update_action} {self.updated}; "
            f"skipped {self.skipped}."
        )


def _normalize_header(value: str) -> str:
    """Normalize a CSV header for alias matching."""
    return value.strip().lower().replace(" ", "_")


def _canonical_headers(fieldnames: Sequence[str | None]) -> list[str]:
    """Return canonical CSV headers or raise when unsupported."""
    if not fieldnames:
        raise ValidationError(
            "Resident CSV is missing a header row.",
            payload={"supported_columns": sorted(set(_HEADER_ALIASES.values()))},
        )

    canonical_headers: list[str] = []
    seen_headers: set[str] = set()
    unknown_headers: list[str] = []
    for raw_header in fieldnames:
        header = str(raw_header or "").strip()
        if not header:
            raise ValidationError("Resident CSV contains a blank header cell.")

        canonical = _HEADER_ALIASES.get(_normalize_header(header))
        if canonical is None:
            unknown_headers.append(header)
            continue
        if canonical in seen_headers:
            raise ValidationError(
                f"Resident CSV contains duplicate column: {canonical}.",
            )
        seen_headers.add(canonical)
        canonical_headers.append(canonical)

    if unknown_headers:
        raise ValidationError(
            "Resident CSV contains unsupported columns.",
            payload={
                "unsupported_columns": unknown_headers,
                "supported_columns": sorted(set(_HEADER_ALIASES.values())),
            },
        )
    if "name" not in seen_headers:
        raise ValidationError("Resident CSV must include a name column.")

    return canonical_headers


def _normalized_email(value: str, *, row_number: int) -> str | None:
    """Validate and normalize an email value."""
    try:
        return normalize_email(value)
    except EmailNotValidError as exc:
        raise ValidationError(
            f"Row {row_number}: invalid email address {value!r}."
        ) from exc


def _normalized_class_year(value: str, *, row_number: int) -> str | None:
    """Normalize a class-year value or raise when unsupported."""
    canonical = canonicalize_class_year(value, CLASS_YEAR_ALIASES)
    if canonical is None:
        return None
    if canonical not in Resident.CLASS_YEARS:
        raise ValidationError(
            f"Row {row_number}: invalid class_year {value!r}. "
            f"Expected one of {Resident.CLASS_YEARS} or aliases "
            "CA1/CA2/CA3."
        )
    return canonical


def _optional_int(value: str, *, row_number: int, field_name: str) -> int | None:
    """Parse an optional integer field."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError(
            f"Row {row_number}: invalid {field_name} value {value!r}; "
            "expected an integer."
        ) from exc


def _optional_date(value: str, *, row_number: int, field_name: str) -> date | None:
    """Parse an optional ISO date field."""
    if not value:
        return None
    try:
        return parse_iso_date(value)
    except ValueError as exc:
        raise ValidationError(
            f"Row {row_number}: invalid {field_name} value {value!r}; "
            "expected YYYY-MM-DD."
        ) from exc


def _optional_bool(value: str, *, row_number: int, field_name: str) -> bool | None:
    """Parse an optional boolean field."""
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValidationError(
        f"Row {row_number}: invalid {field_name} value {value!r}; expected true/false."
    )


def parse_resident_csv(csv_content: str) -> list[ResidentCsvRecord]:
    """Parse a resident bootstrap CSV into normalized records."""
    csv_reader = csv.DictReader(StringIO(csv_content))
    csv_reader.fieldnames = _canonical_headers(csv_reader.fieldnames or [])

    records: list[ResidentCsvRecord] = []
    seen_keys: set[str] = set()
    for row_number, raw_row in enumerate(csv_reader, start=2):
        row = {
            key: value if isinstance(value, str) else ""
            for key, value in raw_row.items()
            if key is not None
        }
        if not any(value.strip() for value in row.values()):
            continue

        name = clean_text(row.get("name"))
        if not name:
            raise ValidationError(f"Row {row_number}: name is required.")

        first_name = clean_text(row.get("first_name")) or None
        last_name = clean_text(row.get("last_name")) or None
        if first_name is None and last_name is None:
            first_name, last_name = split_name(name)

        epic_id = clean_text(row.get("epic_id")) or None
        file_identity = epic_id or name.casefold()
        if file_identity in seen_keys:
            raise ValidationError(
                f"Row {row_number}: duplicate resident entry for {name!r}."
            )
        seen_keys.add(file_identity)

        record = ResidentCsvRecord(
            row_number=row_number,
            name=name,
            first_name=first_name,
            last_name=last_name,
            epic_id=epic_id,
            class_year=_normalized_class_year(
                clean_text(row.get("class_year")),
                row_number=row_number,
            ),
            email=_normalized_email(
                clean_text(row.get("email")),
                row_number=row_number,
            ),
            phone=clean_text(row.get("phone")) or None,
            abbreviation=clean_text(row.get("abbreviation")) or None,
            backup_id=clean_text(row.get("backup_id")) or None,
            lawson_id=_optional_int(
                clean_text(row.get("lawson_id")),
                row_number=row_number,
                field_name="lawson_id",
            ),
            hire_date=_optional_date(
                clean_text(row.get("hire_date")),
                row_number=row_number,
                field_name="hire_date",
            ),
            active=_optional_bool(
                clean_text(row.get("active")),
                row_number=row_number,
                field_name="active",
            ),
        )
        records.append(record)

    if not records:
        raise ValidationError("Resident CSV did not contain any resident rows.")
    return records


def load_resident_csv(csv_path: str | Path) -> list[ResidentCsvRecord]:
    """Load and parse a resident CSV file from disk."""
    path = Path(csv_path)
    return parse_resident_csv(path.read_text(encoding="utf-8-sig"))


def _format_audit_value(value: Any) -> Any:
    """Serialize values for audit logging."""
    if isinstance(value, date):
        return value.isoformat()
    return value


def _name_matches(name: str) -> list[Resident]:
    """Return residents with an exact matching display name."""
    return Resident.query.filter_by(name=name).all()


def _resolve_existing_resident(record: ResidentCsvRecord) -> Resident | None:
    """Resolve a CSV row to an existing resident or raise on conflicts."""
    residents_by_name = _name_matches(record.name)
    if len(residents_by_name) > 1:
        raise ConflictError(
            f"Row {record.row_number}: multiple residents already exist with "
            f"name {record.name!r}; cannot resolve safely."
        )
    resident_by_name = residents_by_name[0] if residents_by_name else None
    resident_by_epic = (
        Resident.get_by_epic_id(record.epic_id) if record.epic_id is not None else None
    )

    if (
        resident_by_name is not None
        and resident_by_epic is not None
        and resident_by_name.id != resident_by_epic.id
    ):
        raise ConflictError(
            f"Row {record.row_number}: EPIC ID {record.epic_id!r} belongs to "
            f"{resident_by_epic.name!r}, but the name column matches "
            f"{resident_by_name.name!r}."
        )

    return resident_by_epic or resident_by_name


def _update_field(
    resident: Resident,
    changes: dict[str, dict[str, Any]],
    field_name: str,
    new_value: Any,
) -> None:
    """Update one resident field and capture the audit diff."""
    old_value = getattr(resident, field_name)
    if old_value == new_value:
        return
    changes[field_name] = {
        "old": _format_audit_value(old_value),
        "new": _format_audit_value(new_value),
    }
    setattr(resident, field_name, new_value)


def _apply_record_to_resident(
    resident: Resident,
    record: ResidentCsvRecord,
) -> dict[str, dict[str, Any]]:
    """Apply a CSV record to an existing resident and return the change set."""
    changes: dict[str, dict[str, Any]] = {}
    _update_field(resident, changes, "name", record.name)
    _update_field(resident, changes, "first_name", record.first_name)
    _update_field(resident, changes, "last_name", record.last_name)

    for field_name in (
        "epic_id",
        "class_year",
        "email",
        "phone",
        "abbreviation",
        "backup_id",
        "lawson_id",
        "hire_date",
    ):
        value = getattr(record, field_name)
        if value is not None:
            _update_field(resident, changes, field_name, value)

    if record.active is not None:
        _update_field(resident, changes, "active", record.active)

    return changes


def import_resident_csv_records(
    records: Sequence[ResidentCsvRecord],
    *,
    user: str | None = None,
    dry_run: bool = False,
) -> ResidentCsvImportResult:
    """Create/update residents from parsed CSV records."""
    created = 0
    updated = 0
    skipped = 0
    created_residents: list[Resident] = []
    updated_residents: list[tuple[Resident, dict[str, dict[str, Any]]]] = []

    for record in records:
        resident = _resolve_existing_resident(record)
        if resident is None:
            resident = Resident(
                name=record.name,
                first_name=record.first_name,
                last_name=record.last_name,
                epic_id=record.epic_id,
                class_year=record.class_year,
                email=record.email,
                phone=record.phone,
                abbreviation=record.abbreviation,
                backup_id=record.backup_id,
                lawson_id=record.lawson_id,
                hire_date=record.hire_date,
                active=True if record.active is None else record.active,
            )
            db.session.add(resident)
            created_residents.append(resident)
            created += 1
            continue

        changes = _apply_record_to_resident(resident, record)
        if changes:
            updated_residents.append((resident, changes))
            updated += 1
        else:
            skipped += 1

    if dry_run:
        db.session.rollback()
        return ResidentCsvImportResult(
            total_records=len(records),
            created=created,
            updated=updated,
            skipped=skipped,
            dry_run=True,
        )

    def _persist() -> ResidentCsvImportResult:
        db.session.flush()

        for resident in created_residents:
            log_create(
                "Resident",
                resident.id,
                payroll_resident_details(resident, source="resident_csv_import"),
            )
        for resident, changes in updated_residents:
            if payroll_changes := filter_payroll_resident_changes(changes):
                log_update("Resident", resident.id, changes=payroll_changes)
        log_import(
            "resident_csv",
            f"Created: {created}, Updated: {updated}, Skipped: {skipped}",
            user=user,
        )
        return ResidentCsvImportResult(
            total_records=len(records),
            created=created,
            updated=updated,
            skipped=skipped,
            dry_run=False,
        )

    result = commit_or_rollback(_persist)

    logger.info(
        "Resident CSV import completed. created=%s updated=%s skipped=%s",
        created,
        updated,
        skipped,
    )
    return result


def import_residents_csv_file(
    csv_path: str | Path,
    *,
    user: str | None = None,
    dry_run: bool = False,
) -> ResidentCsvImportResult:
    """Load, validate, and apply a resident CSV file."""
    records = load_resident_csv(csv_path)
    return import_resident_csv_records(records, user=user, dry_run=dry_run)
