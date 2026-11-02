"""Public visitor forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length, Optional

class TrackLookupForm(FlaskForm):
    order_code = StringField('Order Code', validators=[
        DataRequired(message='Please enter your order code (e.g. TSH-7K2M9).')
    ])
    submit = SubmitField('Track Sneaker Status')

class DeletionRequestForm(FlaskForm):
    customer_name = StringField('Your Full Name', validators=[
        DataRequired(message='Please enter your name as provided at drop-off.')
    ])
    phone = StringField('WhatsApp Mobile Number', validators=[
        DataRequired(message='Please provide the phone number used at drop-off.')
    ])
    notes = TextAreaField('Additional Notes / Specific Orders to Erase', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Submit POPIA Data Deletion Request')
