from datetime import UTC, datetime

from flask_sqlalchemy import SQLAlchemy

from .config import Config
from .holidays import is_weekend_or_holiday

db = SQLAlchemy()


class Resident(db.Model):
    __tablename__ = "residents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    epic_id = db.Column(db.String(50), unique=True, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))

    # Additional staff information
    class_year = db.Column(db.String(20), nullable=True)  # CA1, CA2, CA3, Fellow, OMFS
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    abbreviation = db.Column(db.String(10), nullable=True)
    backup_id = db.Column(db.String(50), nullable=True)

    # Relationship to time entries
    time_entries = db.relationship(
        "TimeEntry", back_populates="resident", cascade="all, delete-orphan"
    )

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
    def active_entries(self):
        """Time entries that are not submitted"""
        return [entry for entry in self.time_entries if not entry.submitted]

    def to_dict(self, include_entries=False):
        """
        Serialize resident to dictionary.

        Args:
            include_entries: Whether to include time entries in output

        Returns:
            Dictionary representation of resident
        """
        data = {
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
        }

        if include_entries:
            data["time_entries"] = [
                {
                    "id": entry.id,
                    "date": entry.date.isoformat(),
                    "role": entry.role.name if entry.role else None,
                }
                for entry in self.time_entries
            ]

        return data

    @classmethod
    def get_active(cls):
        """Get all active residents"""
        return cls.query.filter_by(active=True).order_by(cls.name).all()

    @classmethod
    def get_by_epic_id(cls, epic_id):
        """Find resident by EPIC ID"""
        return cls.query.filter_by(epic_id=epic_id).first()

    @classmethod
    def get_or_create(cls, name, epic_id=None):
        """
        Get existing resident or create new one.

        Args:
            name: Resident name
            epic_id: Optional EPIC ID

        Returns:
            Tuple of (resident, created) where created is boolean
        """
        if epic_id:
            resident = cls.get_by_epic_id(epic_id)
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

    def get_entries_for_period(self, start_date, end_date):
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

    def get_total_overtime(self, start_date=None, end_date=None):
        """
        Calculate total overtime hours for this resident.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Total overtime hours as float
        """
        entries = self.time_entries
        if start_date and end_date:
            entries = self.get_entries_for_period(start_date, end_date)

        return sum(entry.overtime_hours for entry in entries)

    def __repr__(self):
        return f"<Resident {self.name}>"


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    cutoff_hour = db.Column(
        db.Integer, default=17
    )  # Default cutoff hour for overtime calculation (17:30)
    cutoff_minute = db.Column(db.Integer, default=30)  # Default cutoff minute (17:30)
    display_order = db.Column(db.Integer, default=0)
    is_backup = db.Column(
        db.Boolean, default=False
    )  # Backup roles get full overtime on weekends/holidays

    # Relationship to time entries
    time_entries = db.relationship(
        "TimeEntry", back_populates="role", cascade="all, delete-orphan"
    )

    @property
    def cutoff_time_str(self):
        """Return cutoff time as string in 24h format"""
        return f"{self.cutoff_hour:02d}:{self.cutoff_minute:02d}"

    def __repr__(self):
        return f"<Role {self.name}>"


class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    # Time fields
    stop_time = db.Column(db.Time)
    exit_time = db.Column(db.Time)
    start_time = db.Column(db.Time, nullable=True)  # Call-in time for backup roles

    # Status
    locked = db.Column(db.Boolean, default=False)
    submitted = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    # Relationships
    resident = db.relationship("Resident", back_populates="time_entries")
    role = db.relationship("Role", back_populates="time_entries")

    @property
    def overtime_hours(self):
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
        cutoff_hour = self.role.cutoff_hour
        cutoff_minute = (
            self.role.cutoff_minute if hasattr(self.role, "cutoff_minute") else 30
        )
        cutoff_time_decimal = cutoff_hour + cutoff_minute / 60.0
        exit_hour = self.exit_time.hour
        exit_minute = self.exit_time.minute
        exit_time_decimal = exit_hour + exit_minute / 60.0

        # Distinguish overnight shifts from same-day early exits
        # Overnight threshold: exit times before this are treated as next-day
        overnight_threshold = Config.DAY_RESET_HOUR

        if exit_time_decimal < cutoff_time_decimal:
            if exit_time_decimal < overnight_threshold:
                # Early morning exit (before half-cutoff) - overnight shift
                # Add 24 hours to treat as next day
                exit_time_decimal += 24.0
            else:
                # Exit before cutoff but after threshold - same-day early departure
                return 0.0

        # Calculate overtime
        overtime = exit_time_decimal - cutoff_time_decimal

        return round(overtime, 2) if overtime > 0 else 0.0

    def __repr__(self):
        resident_name = self.resident.name if self.resident else "Unknown"
        return f"<TimeEntry {self.date} - {resident_name}>"


class DailySheet(db.Model):
    __tablename__ = "daily_sheets"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False, index=True)
    locked = db.Column(db.Boolean, default=False)
    locked_by = db.Column(db.String(100), nullable=True)
    locked_at = db.Column(db.DateTime, nullable=True)
    submitted = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    def __repr__(self):
        return f"<DailySheet {self.date}>"


class AuditLog(db.Model):
    """Audit log to track all changes in the system"""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(
        db.DateTime, default=datetime.now(UTC), nullable=False, index=True
    )
    user = db.Column(db.String(100), nullable=False)
    action = db.Column(
        db.String(50), nullable=False
    )  # CREATE, UPDATE, DELETE, LOCK, UNLOCK, IMPORT
    entity_type = db.Column(
        db.String(50), nullable=False
    )  # TimeEntry, DailySheet, Resident, etc.
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON string with change details
    ip_address = db.Column(db.String(45), nullable=True)

    def __repr__(self):
        return (
            f"<AuditLog {self.timestamp} - "
            f"{self.user} {self.action} {self.entity_type}>"
        )


class Holiday(db.Model):
    """Holiday dates for overtime calculation"""

    __tablename__ = "holidays"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    is_federal = db.Column(
        db.Boolean, default=False
    )  # True = auto-calculated federal holiday
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))

    @classmethod
    def is_holiday(cls, check_date):
        """Check if a date is a holiday"""
        return cls.query.filter_by(date=check_date).first() is not None

    def __repr__(self):
        return f"<Holiday {self.date} - {self.name}>"
