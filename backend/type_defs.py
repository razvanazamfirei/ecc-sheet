from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from .models import AuditLog, Resident, TimeEntry


class ResidentTimeEntryDict(TypedDict):
    id: int
    date: str
    role: str | None


class ResidentDict(TypedDict):
    id: int
    name: str
    epic_id: str | None
    active: bool
    created_at: str | None
    status: str
    total_entries: int
    class_year: str | None
    email: str | None
    phone: str | None
    abbreviation: str | None
    backup_id: str | None
    first_name: str | None
    last_name: str | None
    lawson_id: int | None
    hire_date: str | None
    time_entries: NotRequired[list[ResidentTimeEntryDict]]


class StaffRecord(TypedDict):
    name: str
    epic_id: str
    class_year: str
    backup_id: str
    abbreviation: str
    phone: str
    email: str | None


class ImportResult(TypedDict):
    success: bool
    created: int
    updated: int
    skipped: int
    total_records: int
    error: str | None


class ResidentEntryDict(TypedDict):
    date: str
    role: str
    exit_time: str
    overtime: float


class ResidentSummaryDict(TypedDict):
    name: str
    entries: list[ResidentEntryDict]
    total_overtime: float


class ResidentFieldChange(TypedDict):
    old: str | None
    new: str | None


type ScheduleResidentChanges = dict[str, ResidentFieldChange]


class ScheduleImportResult(TypedDict):
    entries_created: int
    created_residents: list[Resident]
    updated_residents: list[tuple[Resident, ScheduleResidentChanges]]
    created_entries: list[TimeEntry]
    skipped_unknown_residents: int
    skipped_weekday_backups: int


type ResidentData = dict[int, ResidentSummaryDict]

type ResidentID = int | str | None

type AuditLogs = list[AuditLog]

type TimeEntries = Sequence[TimeEntry]

type StaffList = list[StaffRecord]
