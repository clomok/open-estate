from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, BooleanField, SubmitField, TextAreaField, DateField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, Optional
from datetime import date

# Standard Asset Types
ASSET_TYPES = [
    ('Property', 'Real Estate Property'),
    ('Financial', 'Bank/Investment Account'),
    ('Vehicle', 'Vehicle'),
    ('Personal', 'Personal Item (Jewelry/Art)'),
    ('Liability', 'Debt/Loan')
]

# --- Base Asset Forms (Previous code remains here) ---
class BaseAssetForm(FlaskForm):
    name = StringField('Name / Title', validators=[DataRequired(), Length(max=150)])
    asset_type = StringField('Asset Type', validators=[DataRequired()]) 
    is_in_trust = BooleanField('Held in Trust?')
    owner_id = SelectField('Individual Owner', coerce=int, validators=[Optional()])
    notes = TextAreaField('General Notes')
    submit = SubmitField('Save Item')

class RealEstateForm(BaseAssetForm):
    address = StringField('Property Address')
    apn_number = StringField('APN / Parcel Number')
    purchase_date = StringField('Date Purchased (YYYY-MM-DD)')
    purchase_price = FloatField('Purchase Price ($)', validators=[Optional()])
    current_value = FloatField('Estimated Current Value ($)', validators=[Optional()])

class VehicleForm(BaseAssetForm):
    year = StringField('Year')
    make = StringField('Make')
    model = StringField('Model')
    vin = StringField('VIN')
    license_plate = StringField('License Plate')
    location_keys = StringField('Spare Keys Location')
    current_value = FloatField('Estimated Value ($)', validators=[Optional()])

class BankAccountForm(BaseAssetForm):
    institution = StringField('Bank / Institution Name')
    account_number = StringField('Account Number (Last 4)')
    routing_number = StringField('Routing Number')
    account_type = SelectField('Account Type', choices=[
        ('Checking', 'Checking'), 
        ('Savings', 'Savings'), 
        ('CD', 'Certificate of Deposit'),
        ('SafeDeposit', 'Safe Deposit Box')
    ])
    current_value = FloatField('Current Balance ($)', validators=[Optional()])

class InvestmentForm(BaseAssetForm):
    institution = StringField('Brokerage / Firm')
    account_number = StringField('Account Number')
    advisor_name = StringField('Advisor Name')
    advisor_contact = StringField('Advisor Phone/Email')
    current_value = FloatField('Total Portfolio Value ($)', validators=[Optional()])

class LiabilityForm(BaseAssetForm):
    lender = StringField('Lender / Creditor')
    account_number = StringField('Account Number')
    interest_rate = StringField('Interest Rate (%)')
    due_date = StringField('Monthly Due Date')
    outstanding_balance = FloatField('Outstanding Balance ($)', validators=[DataRequired()])

class PersonalItemForm(BaseAssetForm):
    description = TextAreaField('Detailed Description')
    location = StringField('Physical Location (e.g. Safe)')
    appraisal_date = StringField('Date Appraised')
    appraiser_info = StringField('Appraiser Contact')
    current_value = FloatField('Appraised Value ($)', validators=[Optional()])

class UtilityForm(BaseAssetForm):
    provider = StringField('Provider (e.g. PG&E)')
    account_number = StringField('Account Number')
    login_username = StringField('Login Username')
    autopay_status = SelectField('Autopay?', choices=[('Yes', 'Yes'), ('No', 'No'), ('Unknown', 'Unknown')])
    current_value = FloatField('Average Monthly Cost (Reference Only)', validators=[Optional()])

def get_form_class(type_code):
    mapping = {
        'RealEstate': RealEstateForm,
        'Vehicle': VehicleForm,
        'Bank': BankAccountForm,
        'Investment': InvestmentForm,
        'Liability': LiabilityForm,
        'Jewelry': PersonalItemForm,
        'Art': PersonalItemForm,
        'Utility': UtilityForm,
        'Other': BaseAssetForm
    }
    return mapping.get(type_code, BaseAssetForm)

# --- NEW: Appraisal Form ---
class AppraisalForm(FlaskForm):
    date = DateField('Date of Valuation', default=date.today, validators=[DataRequired()])
    value = FloatField('New Value ($)', validators=[DataRequired()])
    source = StringField('Source (e.g. Zillow, KBB, Statement)', validators=[Length(max=100)])
    notes = TextAreaField('Notes')
    submit = SubmitField('Add Valuation')