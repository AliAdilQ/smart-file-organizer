"""Validated forms shared by user and admin workspaces."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Length, NumberRange, Email, Optional
from app.organizer.rules import MODES


class OrganizerForm(FlaskForm):
    folder = StringField('Source folder', validators=[DataRequired(), Length(max=2048)])
    mode = SelectField('Organize by', choices=list(MODES.items()))


class RuleForm(FlaskForm):
    name = StringField('Rule name', validators=[DataRequired(), Length(max=80)])
    extensions = StringField('Extensions', validators=[DataRequired(), Length(max=512)])
    destination = StringField('Destination folder', validators=[DataRequired(), Length(max=240)])
    priority = IntegerField('Priority (lower runs first)', default=100, validators=[NumberRange(min=0, max=10000)])
    is_active = BooleanField('Enabled', default=True)


class ScheduleForm(OrganizerForm):
    name = StringField('Task name', validators=[Optional(), Length(max=120)])
    frequency = SelectField('Frequency', choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')])
    rule_id = SelectField('Rule', coerce=int, choices=[])
    consent = BooleanField('I authorize automatic moves in this folder on this schedule.', validators=[DataRequired()])


class ProfileForm(FlaskForm):
    email = StringField('Email address', validators=[DataRequired(), Email(), Length(max=254)])
    current_password = PasswordField('Current password', validators=[DataRequired(), Length(max=256)])
    password = PasswordField('New password (optional)', validators=[Optional(), Length(min=10, max=256)])
