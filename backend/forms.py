"""
WTForms with CSRF protection and validation
"""

import re

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    TimeField,
)
from wtforms.validators import DataRequired, Length, NumberRange, ValidationError


class TimeEntryForm(FlaskForm):
    """Form for adding/editing time entries with validation"""

    resident_id = SelectField("Resident", coerce=int, validators=[DataRequired()])
    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    exit_time = TimeField("Exit Time", validators=[DataRequired()])
    airway_assist = BooleanField("Airway Assist")
    emergency = BooleanField("Emergency")
    dinner_break = BooleanField("Dinner Break")
    paper_record = BooleanField("Paper Record")


def validate_name(field):
    """Validate resident name - only letters, spaces, hyphens, apostrophes"""
    if not re.match(r"^[A-Za-z\s\-'.]+$", field.data):
        raise ValidationError(
            "Name can only contain letters, spaces, hyphens, and apostrophes"
        )


class ResidentForm(FlaskForm):
    """Form for adding residents with validation"""

    name = StringField(
        "Name",
        validators=[
            DataRequired(),
            Length(min=2, max=100, message="Name must be between 2 and 100 characters"),
        ],
    )


class RoleUpdateForm(FlaskForm):
    """Form for updating role cutoff hours"""

    cutoff_hour = IntegerField(
        "Cutoff Hour",
        validators=[
            DataRequired(),
            NumberRange(min=0, max=23, message="Hour must be between 0 and 23"),
        ],
    )


class ReportForm(FlaskForm):
    """Form for generating reports"""

    start_date = DateField("Start Date", validators=[DataRequired()])
    end_date = DateField("End Date", validators=[DataRequired()])

    def validate_end_date(self, field):
        """Ensure end date is after start date"""
        if self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("End date must be after start date")
