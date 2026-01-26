"""
WTForms with CSRF protection and validation
"""

from flask_wtf import FlaskForm
from wtforms import (
    DateField,
    IntegerField,
    SelectField,
    StringField,
    TimeField,
    ValidationError,
)
from wtforms.validators import DataRequired, Length, NumberRange


class TimeEntryForm(FlaskForm):
    """Form for adding/editing time entries with validation"""

    resident_id = SelectField("Resident", coerce=int, validators=[DataRequired()])
    role_id = SelectField("Role", coerce=int, validators=[DataRequired()])
    exit_time = TimeField("Exit Time", validators=[DataRequired()])


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
        """Validate that end_date is not before start_date."""
        if self.start_date.data and field.data:
            if field.data < self.start_date.data:
                raise ValidationError("End date must be on or after start date")
