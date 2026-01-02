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

# --- Base Asset Forms ---
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

def get_form_class(type_code):
    mapping = {
        'RealEstate': RealEstateForm,
        'Vehicle': VehicleForm,
        'Bank': BankAccountForm,
        'Investment': InvestmentForm,
        'Liability': LiabilityForm,
        'Jewelry': PersonalItemForm,
        'Art': PersonalItemForm,
        'Other': BaseAssetForm
    }
    return mapping.get(type_code, BaseAssetForm)

# --- Appraisal Form ---
class AppraisalForm(FlaskForm):
    date = DateField('Date of Valuation', default=date.today, validators=[DataRequired()])
    value = FloatField('New Value ($)', validators=[DataRequired()])
    source = StringField('Source (e.g. Zillow, KBB, Statement)', validators=[Length(max=100)])
    notes = TextAreaField('Notes')
    submit = SubmitField('Add Valuation')

# --- Person/Contact Form ---
class PersonForm(FlaskForm):
    name = StringField('Name / Organization', validators=[DataRequired(), Length(max=100)])
    role = SelectField('Role / Relationship', choices=[
        ('Trustor', 'Trustor (Grantor)'),
        ('Trustee', 'Trustee'),
        ('Beneficiary', 'Beneficiary'),
        ('Executor', 'Executor'),
        ('Attorney', 'Attorney'),
        ('Financial Advisor', 'Financial Advisor'),
        ('Accountant', 'Accountant / CPA'),
        ('Funeral Director', 'Funeral Service'),
        ('Medical', 'Doctor / Medical POC'),
        ('Insurance', 'Insurance Agent'),
        ('Vendor', 'Vendor / Service Provider'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    
    email = StringField('Email', validators=[Optional(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Physical Address', validators=[Optional()])
    notes = TextAreaField('Notes / Instructions', validators=[Optional()])
    submit = SubmitField('Save Contact')

# --- PHASE 5: REAL ESTATE EXPANSION FORMS ---

class StructureForm(FlaskForm):
    name = StringField('Structure Name', validators=[DataRequired()], render_kw={"placeholder": "e.g. North Garden Shed"})
    structure_type = StringField('Type', render_kw={"placeholder": "e.g. Outbuilding, Deck, Pool"})
    description = TextAreaField('Description')
    date_last_maintained = DateField('Last Maintained', validators=[Optional()])
    notes = TextAreaField('Maintenance Notes')
    submit = SubmitField('Save Structure')

class LocationPointForm(FlaskForm):
    label = StringField('Label', validators=[DataRequired()], render_kw={"placeholder": "e.g. Septic Tank Lid"})
    description = TextAreaField('Description', render_kw={"placeholder": "e.g. Buried 6 inches deep..."})
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    submit = SubmitField('Save Pin')

class RecurringBillForm(FlaskForm):
    name = StringField('Bill Name', validators=[DataRequired()], render_kw={"placeholder": "e.g. Property Tax"})
    payee = StringField('Payee', render_kw={"placeholder": "e.g. County Treasurer"})
    account_number = StringField('Account Number')
    amount_estimated = FloatField('Est. Amount ($)', validators=[Optional()])
    frequency = SelectField('Frequency', choices=[('Monthly', 'Monthly'), ('Annual', 'Annual'), ('Quarterly', 'Quarterly')])
    is_autopay = BooleanField('Autopay Enabled?')
    next_due_date = DateField('Next Due Date', validators=[Optional()])
    submit = SubmitField('Save Bill')

class AssetVendorForm(FlaskForm):
    person_id = SelectField('Select Contact', coerce=int, validators=[DataRequired()])
    role = StringField('Service Role', validators=[DataRequired()], render_kw={"placeholder": "e.g. Pool Cleaner, Gardener"})
    notes = TextAreaField('Notes', render_kw={"placeholder": "Account #, Gate Code for them..."})
    submit = SubmitField('Assign Vendor')