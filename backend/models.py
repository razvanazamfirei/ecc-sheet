from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from datetime import date as dt_date
from typing import TYPE_CHECKING, ClassVar, Final, override

from email_validator import EmailNotValidError
from email_validator import validate_email as _validate_email
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from .config import Config
from .holidays import is_weekend_or_holiday
from .type_defs import ResidentDict, ResidentTimeEntryDict

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


db: SQLAlchemy = SQLAlchemy(model_class=Base)

if TYPE_CHECKING:
    from flask_sqlalchemy.query import Query

    class ModelBase(Base):
        query: ClassVar[Query]
else:
    ModelBase = db.Model


class Resident(ModelBase):
    __tablename__ = "residents"

    CLASS_YEARS: ClassVar[list[str]] = ["CA-1", "CA-2", "CA-3", "Fellow", "OMFS"]

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    epic_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    # Additional staff information
    class_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(10), nullable=True)
    backup_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lawson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Relationship to time entries
    time_entries: Mapped[list[TimeEntry]] = relationship(
        "TimeEntry", back_populates="resident", cascade="all, delete-orphan"
    )

    @validates("class_year")
    def validate_class_year(self, _key: str, value: str | None) -> str | None:
        value = value.strip() if isinstance(value, str) else value
        if not value:
            return None
        if value not in self.CLASS_YEARS:
            logger.warning(
                "Invalid class_year %r discarded for Resident(id=%r); "
                "must be one of %s",
                value,
                self.id,
                self.CLASS_YEARS,
            )
            return None
        return value

    @validates("email")
    def validate_email(self, _key: str, value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        try:
            result = _validate_email(value, check_deliverability=False)
            return result.normalized
        except EmailNotValidError:
            logger.warning(
                "Invalid email %r discarded for Resident(id=%r)", value, self.id
            )
            return None

    @property
    def display_name(self) -> str:
        """Formatted display name"""
        return self.name

    @property
    def status(self) -> str:
        """Human-readable status"""
        return "Active" if self.active else "Inactive"

    @property
    def total_entries(self) -> int:
        """Total number of time entries for this resident"""
        return len(self.time_entries)

    @property
    def active_entries(self) -> list[TimeEntry]:
        """Time entries that are not submitted"""
        return [entry for entry in self.time_entries if not entry.submitted]

    def to_dict(self, *, include_entries: bool = False) -> ResidentDict:
        """
        Serialize resident to dictionary.

        Args:
            include_entries: Whether to include time entries in output

        Returns:
            Dictionary representation of resident
        """
        data: ResidentDict = {
            "id": self.id,
            "name": self.name,
            "epic_id": self.epic_id,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
            "total_entries": self.total_entries,
            "class_year": self.class_year,
            "email": self.email,
            "phone": self.phone,
            "abbreviation": self.abbreviation,
            "backup_id": self.backup_id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "lawson_id": self.lawson_id,
            "hire_date": self.hire_date.isoformat() if self.hire_date else None,
        }

        if include_entries:
            data["time_entries"] = [
                ResidentTimeEntryDict(
                    id=entry.id,
                    date=entry.date.isoformat(),
                    role=entry.role.name if entry.role else None,
                )
                for entry in self.time_entries
            ]

        return data

    @classmethod
    def get_active(cls) -> list[Resident]:
        """Get all active residents"""
        return cls.query.filter_by(active=True).order_by(cls.name).all()

    @classmethod
    def get_by_epic_id(cls, epic_id: str) -> Resident | None:
        """Find resident by EPIC ID"""
        return cls.query.filter_by(epic_id=epic_id).first()

    @classmethod
    def get_or_create(
        cls, name: str, epic_id: str | None = None
    ) -> tuple[Resident, bool]:
        """
        Get existing resident or create new one.

        Args:
            name: Resident name
            epic_id: Optional EPIC ID

        Returns:
            Tuple of (resident, created) where created is boolean
        """
        if epic_id:
            resident: Resident | None = cls.get_by_epic_id(epic_id)
            if resident:
                return resident, False

        resident = cls.query.filter_by(name=name).first()
        if resident:
            if epic_id and not resident.epic_id:
                resident.epic_id = epic_id
            return resident, False

        resident = cls(name=name, epic_id=epic_id)
        db.session.add(resident)
        return resident, True

    def get_entries_for_period(
        self, start_date: date, end_date: date
    ) -> list[TimeEntry]:
        """
        Get time entries for this resident within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of TimeEntry objects
        """
        return TimeEntry.query.filter(
            TimeEntry.resident_id == self.id,
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        ).all()

    def get_total_overtime(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> float:
        """
        Calculate total overtime hours for this resident.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total overtime hours as float
        """
        query = TimeEntry.query.filter(TimeEntry.resident_id == self.id)
        if start_date is not None:
            query = query.filter(TimeEntry.date >= start_date)
        if end_date is not None:
            query = query.filter(TimeEntry.date <= end_date)
        return sum(entry.overtime_hours for entry in query.all())

    @override
    def __repr__(self) -> str:
        return f"<Resident {self.name}>"


class Role(ModelBase):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    cutoff_hour: Mapped[int] = mapped_column(
        Integer, default=Config.DEFAULT_CUTOFF_HOUR
    )  # Default cutoff hour for overtime calculation (17:30)
    cutoff_minute: Mapped[int] = mapped_column(
        Integer, default=Config.DEFAULT_CUTOFF_MINUTE
    )  # Default cutoff minute (17:30)
    display_order: Mapped[int | None] = mapped_column(Integer, default=0)
    is_backup: Mapped[bool] = mapped_column(Boolean, default=False)
    is_call_team: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Call team roles: shown on sheet but never generate overtime

    # Relationship to time entries
    time_entries: Mapped[list[TimeEntry]] = relationship(
        "TimeEntry", back_populates="role", passive_deletes=True
    )

    @property
    def cutoff_time_str(self) -> str:
        """Return cutoff time as string in 24h format"""
        return f"{self.cutoff_hour:02d}:{self.cutoff_minute:02d}"

    @override
    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class TimeEntry(ModelBase):
    __tablename__ = "time_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), nullable=False)
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"), nullable=True
    )

    # Time fields
    stop_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    exit_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Status
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    resident: Mapped[Resident] = relationship("Resident", back_populates="time_entries")
    role: Mapped[Role | None] = relationship("Role", back_populates="time_entries")

    @property
    def overtime_hours(self) -> float:
        """
        Calculate hours worked after cutoff time.
        AM exit times (before cutoff) are treated as next day (overnight shifts).

        For backup roles on weekends/holidays, all time from start_time to exit_time
        counts as overtime.

        Example:
        - Cutoff: 17:30
        - Exit: 02:30 AM -> Treated as 26:30 (next day) -> 9.0 hours overtime
        - Exit: 16:00 -> Same day early exit -> 0 hours overtime
        - Exits: 20:00 -> Same day -> 2.5 hours overtime
        - Backup role on Saturday, start: 09:00, exit: 17:00 -> 8.0 hours overtime
        """
        if not self.exit_time or not self.role:
            return 0.0

        # Call team roles are displayed but never generate overtime
        if self.role.is_call_team:
            return 0.0

        # Check if backup role on weekend/holiday - all time from start is overtime
        if self.role.is_backup and is_weekend_or_holiday(self.date):
            # Default to 08:00 if no start_time is set
            start_decimal = 8.0
            if self.start_time:
                start_decimal = self.start_time.hour + self.start_time.minute / 60.0
            exit_decimal = self.exit_time.hour + self.exit_time.minute / 60.0
            if exit_decimal < start_decimal:
                exit_decimal += 24  # overnight shift
            return round(exit_decimal - start_decimal, 2)

        # Convert cutoff and exit to decimal hours
        cutoff_time_decimal: float = (
            self.role.cutoff_hour + self.role.cutoff_minute / 60.0
        )
        exit_time_decimal: float = self.exit_time.hour + self.exit_time.minute / 60.0

        # Distinguish overnight shifts from same-day early exits
        # Overnight threshold: exit times before this are treated as next-day
        overnight_threshold: int = Config.DAY_RESET_HOUR

        if exit_time_decimal < cutoff_time_decimal:
            if exit_time_decimal < overnight_threshold:
                # Early morning exit (before half-cutoff) - overnight shift
                # Add 24 hours to treat as next day
                exit_time_decimal += 24.0
            else:
                # Exit before cutoff but after threshold - same-day early departure
                return 0.0

        # Calculate overtime
        overtime: float = exit_time_decimal - cutoff_time_decimal
        return round(overtime, 2) if overtime > 0 else 0.0

    @override
    def __repr__(self) -> str:
        return f"<TimeEntry {self.date} - resident_id={self.resident_id}>"


class DailySheet(ModelBase):
    __tablename__ = "daily_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @override
    def __repr__(self) -> str:
        return f"<DailySheet {self.date}>"


class AuditLog(ModelBase):
    """Audit log to track all changes in the system"""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    user: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # CREATE, UPDATE, DELETE, LOCK, UNLOCK, IMPORT
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # TimeEntry, DailySheet, Resident, etc.
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string with change details
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    @override
    def __repr__(self) -> str:
        return (
            f"<AuditLog {self.timestamp} - "
            f"{self.user} {self.action} {self.entity_type}>"
        )


class Holiday(ModelBase):
    """Holiday dates for overtime calculation"""

    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_federal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    @classmethod
    def is_holiday(cls, check_date: dt_date) -> bool:
        """Check if a date is a holiday."""
        return cls.query.filter_by(date=check_date).first() is not None

    @override
    def __repr__(self) -> str:
        return f"<Holiday {self.date} - {self.name}>"


class PayrollLayoutError(ValueError):
    """Raised when a PayrollExportLayout is misconfigured."""


@dataclass(frozen=True)
class PayrollExportLayout:
    headers: tuple[str, ...]
    columns: Mapping[str, int]  # semantic name -> 0-based index

    def __post_init__(self) -> None:
        if not self.columns:
            if self.headers:
                raise PayrollLayoutError("Layout has headers but no column mappings.")
            return
        max_index = max(self.columns.values())
        if len(self.headers) != max_index + 1:
            raise PayrollLayoutError(
                f"Layout mismatch: len(headers)={len(self.headers)} "
                f"but max(columns)+1={max_index + 1}."
            )

    @property
    def n_cols(self) -> int:
        return len(self.headers)


PayrollLayout: Final = PayrollExportLayout(
    headers=(
        "Program",  # A (0)
        "",  # B (1)
        "Employee",  # C (2)
        "Company",  # D (3)
        "Batch",  # E (4)
        "Lawson ID #",  # F (5)
        "filter",  # G (6)
        "Pay Code",  # H (7)
        "Hours",  # I (8)
        "filter 1",  # J (9)
        "filter 2",  # K (10)
        "filter 3",  # L (11)
        "filter 4",  # M (12)
        "Transdate",  # N (13)
        "Dept",  # O (14)
        "Expense",  # P (15)
        "Acct Unit",  # Q (16)
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",  # R..AA (10 empties: 17..26)
        "",  # AB header blank (27)
    ),
    columns={
        "program": 0,
        "hire_date": 1,
        "employee": 2,
        "company": 3,
        "batch": 4,
        "lawson_id": 5,
        "pay_code": 7,
        "hours": 8,
        "transdate": 13,
        "dept": 14,
        "expense": 15,
        "acct_unit": 16,
        "note": 27,
    },
)


class PayrollSettings(ModelBase):
    """Institutional payroll export settings (single-row config table)."""

    __tablename__ = "payroll_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company: Mapped[str | None] = mapped_column(String(50), nullable=True)
    batch: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pay_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dept: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expense: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acct_unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    label_suffix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    layout: ClassVar[PayrollExportLayout] = PayrollLayout

    @property
    def text_format(self) -> str:
        """Excel format string for text columns."""
        return "@"

    @property
    def date_format(self) -> str:
        """Excel format string for date columns."""
        return "mm/dd/yyyy"

    def note_for(self, start_date: date) -> str:
        # "FEB" or "FEB Suffix"
        month = start_date.strftime("%b").upper()
        suffix = (self.label_suffix or "").strip()
        return f"{month} {suffix}".strip()

    def export_codes(self) -> dict[str, str | None]:
        """
        Coerce code-like fields to strings for Excel/import robustness.
        """
        return {
            "program": self.program,
            "company": self.company,
            "batch": str(self.batch) if self.batch is not None else None,
            "pay_code": str(self.pay_code) if self.pay_code is not None else None,
            "dept": str(self.dept) if self.dept is not None else None,
            "expense": str(self.expense) if self.expense is not None else None,
            "acct_unit": str(self.acct_unit) if self.acct_unit is not None else None,
        }

    @classmethod
    def export_text_cols(cls) -> frozenset[int]:
        """
        0-based indices of columns that should be formatted as TEXT in Excel.
        Driven by the export layout.
        """
        c = cls.layout.columns
        return frozenset(
            {
                c["program"],
                c["company"],
                c["batch"],
                c["lawson_id"],
                c["pay_code"],
                c["dept"],
                c["expense"],
                c["acct_unit"],
                c["note"],
            }
        )

    @classmethod
    def get_or_create(cls) -> PayrollSettings:
        """Return the single settings row, creating it with defaults if
        it doesn't exist.

        The row is always stored with id=1 so that the primary-key constraint
        enforces the singleton invariant at the database level.
        """
        settings = db.session.get(cls, 1)
        if settings is None:
            settings = cls(
                id=1,
                program=Config.PAYROLL_PROGRAM,
                company=Config.PAYROLL_COMPANY,
                batch=Config.PAYROLL_BATCH,
                pay_code=Config.PAYROLL_PAY_CODE,
                dept=Config.PAYROLL_DEPT,
                expense=Config.PAYROLL_EXPENSE,
                acct_unit=Config.PAYROLL_ACCT_UNIT,
                label_suffix=Config.PAYROLL_LABEL_SUFFIX,
            )
            db.session.add(settings)
            db.session.commit()
        return settings

    @override
    def __repr__(self) -> str:
        return f"<PayrollSettings program={self.program}>"
