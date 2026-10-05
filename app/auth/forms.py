from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Regexp


class LoginForm(FlaskForm):
    identity = StringField('Username or email', validators=[DataRequired(), Length(max=254)])
    password = PasswordField('Password', validators=[DataRequired(), Length(max=256)])
    submit = SubmitField('Sign in')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64),
                           Regexp(r'^[A-Za-z0-9_]+$', message='Use letters, numbers, and underscores.')])
    email = StringField('Email address', validators=[DataRequired(), Email(), Length(max=254)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=10, max=256)])
    confirm = PasswordField('Confirm password', validators=[EqualTo('password')])
    submit = SubmitField('Create account')
