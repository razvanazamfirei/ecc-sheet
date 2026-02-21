from __future__ import annotations

import logging
from datetime import UTC, datetime, time
from datetime import date as dt_date
from typing import TYPE_CHECKING, ClassVar, override

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


class Resident(ModelBases):
    __tablename__ = "residents"

    CLASS_YEARS: ClassVar[list[str]] = ["CA-1", "CA-2", "CA-3", "Fellow", "OMFS"]

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    epic_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    # Additional staff information
    class_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    abbreviation: Mapped[str | None] = mapped_column(String(10), nullable=True)
    backup_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lawson_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hire_date: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
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

    @property
    def display_name(self):
        """Formatted display name"""
        return self.name

    @property
    def status(self):
        """Human-readable status"""
        return "Active" if self.active else "Inactive"

    @property
    def total_entries(self):
        """Total number of time entries for this resident"""
        return len(self.time_entries)

    @property
    def active_entries(self) -> list[TimeEntry]:
        """Time entries that are not submitted"""
        return [entry for entry in self.time_entries if not entry.submitted]

    def to_dict(self, include_entries: bool = False) -> ResidentDict:
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

        resident = cls()
        resident.name = name
        resident.epic_id = epic_id
        db.session.add(resident)
        return resident, True

    def get_entries_for_period(
        self, start_date: dt_date, end_date: dt_date
    ) -> list[TimeEntry]:
        """
        Get time entries for this resident within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of TimeEntry objects
        """
        return [
            entry for entry in self.time_entries if start_date <= entry.date <= end_date
        ]

    def get_total_overtime(
        self, start_date: dt_date | None = None, end_date: dt_date | None = None
    ) -> float:
        """
        Calculate total overtime hours for this resident.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total overtime hours as float
        """
        entries = (
            self.get_entries_for_period(start_date, end_date)
            if start_date and end_date
            else self.time_entries
        )

        return sum(entry.overtime_hours for entry in entries)

    @override
    def __repr__(self) -> str:
        return f"<Resident {self.name}>"


class Role(ModelBase):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    cutoff_hour: Mapped[int] = mapped_column(
        Integer, default=17
    )  # Default cutoff hour for overtime calculation (17:30)
    cutoff_minute: Mapped[int] = mapped_column(
        Integer, default=30
    )  # Default cutoff minute (17:30)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_backup: Mapped[bool] = mapped_column(Boolean, default=False)
    is_call_team = Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # Call team roles: shown on sheet but never generate overtime

    # Relationship to time entries
    time_entries: Mapped[list[TimeEntry]] = relationship(
        "TimeEntry", back_populates="role", cascade="all, delete-orphan"
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
    date: Mapped[dt_date] = mapped_column(Date, nullable=False, index=True)
    resident_id: Mapped[int] = mapped_column(ForeignKey("residents.id"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)

    # Time fields
    stop_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    exit_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Status
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    resident: Mapped[Resident] = relationship("Resident", back_populates="time_entries")
    role: Mapped[Role] = relationship("Role", back_populates="time_entries")

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
        cutoff_time_decimal: int | float = (
            self.role.cutoff_hour + self.role.cutoff_minute / 60.0
        )
        exit_time_decimal: int | float = (
            self.exit_time.hour + self.exit_time.minute / 60.0
        )

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
        overtime: int | float = exit_time_decimal - cutoff_time_decimal
        return round(overtime, 2) if overtime > 0 else 0.0

    @override
    def __repr__(self) -> str:
        resident_name = self.resident.name if self.resident else "Unknown"
        return f"<TimeEntry {self.date} - {resident_name}>"


class DailySheet(ModelBase):
    __tablename__ = "daily_sheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[dt_date] = mapped_column(Date, unique=True, nullable=False, index=True)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
        DateTime,
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
    date: Mapped[dt_date] = mapped_column(Date, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_federal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    @classmethod
    def is_holiday(cls, check_date: dt_date) -> bool:
        """Check if a date is a holiday."""
        return cls.query.filter_by(date=check_date).first() is not None

    @override
    def __repr__(self) -> str:
        return f"<Holiday {self.date} - {self.name}>"


class PayrollSettings(db.Model):
    """Institutional payroll export settings (single-row config table)."""

    __tablename__ = "payroll_settings"

    id = db.Column(db.Integer, primary_key=True)
    program = db.Column(db.String(50), nullable=True)
    company = db.Column(db.String(50), nullable=True)
    batch = db.Column(db.Integer, nullable=True)
    pay_code = db.Column(db.Integer, nullable=True)
    dept = db.Column(db.Integer, nullable=True)
    expense = db.Column(db.Integer, nullable=True)
    acct_unit = db.Column(db.Integer, nullable=True)
    label_suffix = db.Column(db.String(50), nullable=True)

    @classmethod
    def get_or_create(cls):
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

    def __repr__(self):
        return f"<PayrollSettings program={self.program}>"
