"""Staff operations forms."""
from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from app.models import SERVICE_CHOICES, REFERRAL_SOURCES
from app.utils.security import sanitize_sa_phone

class DropoffForm(FlaskForm):
    customer_name = StringField('Customer Full Name', validators=[
        DataRequired(message='Customer name is required.'),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters.')
    ])
    whatsapp_phone = StringField('WhatsApp Mobile Number', validators=[
        DataRequired(message='South African mobile number is required for order updates.')
    ])
    service = SelectField('Cleaning Service', choices=SERVICE_CHOICES, default='standard', validators=[DataRequired()])
    pairs = IntegerField('Number of Pairs', default=1, validators=[
        DataRequired(), NumberRange(min=1, max=20, message='Pairs must be between 1 and 20.')
    ])
    notes = TextAreaField('Condition & Special Notes (e.g. scuffs, brand, lace color)', validators=[
        Optional(), Length(max=500, message='Notes must be under 500 characters.')
    ])
    source = SelectField('How did they hear about Tshienda?', choices=REFERRAL_SOURCES, default='walk_in')
    popia_consent = BooleanField(
        'Customer explicitly consented to receive order tracking updates via WhatsApp in compliance with POPIA',
        validators=[DataRequired(message='POPIA consent is required before processing any order.')]
    )
    submit = SubmitField('Save Order & Print QR Tag')

    def validate_whatsapp_phone(self, field):
        cleaned = sanitize_sa_phone(field.data)
        if not cleaned:
            raise ValidationError('Please enter a valid South African mobile number (e.g. 082 123 4567 or +27821234567).')

class SettingsForm(FlaskForm):
    price_standard = StringField('Standard Clean Price (ZAR)', validators=[DataRequired()])
    price_deep = StringField('Deep Clean Price (ZAR)', validators=[DataRequired()])
    price_suede_leather = StringField('Suede & Leather Care Price (ZAR)', validators=[DataRequired()])
    whatsapp_template_dropped_off = TextAreaField('Dropped Off Message Template', validators=[DataRequired()])
    whatsapp_template_washing = TextAreaField('Washing Message Template', validators=[DataRequired()])
    whatsapp_template_drying = TextAreaField('Drying Message Template', validators=[DataRequired()])
    whatsapp_template_ready = TextAreaField('Ready for Collection Template', validators=[DataRequired()])
    whatsapp_template_collected = TextAreaField('Collected & Thank You Template', validators=[DataRequired()])
    submit = SubmitField('Update Settings')

class ManualScanForm(FlaskForm):
    order_number = StringField('Enter Order Code (e.g. TSH-7K2M9)', validators=[
        DataRequired(message='Please enter or scan an order number.')
    ])
    submit = SubmitField('Lookup & Advance Stage')
