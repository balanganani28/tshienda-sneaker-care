"""Authentication forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length

class LoginForm(FlaskForm):
    email = StringField('Staff Email', validators=[
        DataRequired(message='Please provide your registered staff email.'),
        Email(message='Please enter a valid email address.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Please enter your password.'),
        Length(min=6, message='Password must be at least 6 characters.')
    ])
    remember = BooleanField('Keep me signed in on this device')
    submit = SubmitField('Sign in to Staff Portal')
