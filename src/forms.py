from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, BooleanField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

# Standard Asset Types
ASSET_TYPES = [
    ('Property', 'Real Estate Property'),
    ('Financial', 'Bank/Investment Account'),
    ('Vehicle', 'Vehicle'),
    ('Personal', 'Personal Item (Jewelry/Art)'),
    ('Liability', 'Debt/Loan')
]

class AssetForm(FlaskForm):
    name = StringField('Asset Name', validators=[
        DataRequired(), 
        Length(min=2, max=150, message="Name must be between 2 and 150 characters")
    ])
    
    asset_type = SelectField('Type', choices=ASSET_TYPES, validators=[DataRequired()])
    
    value_estimated = FloatField('Estimated Value ($)', validators=[
        Optional(),
        NumberRange(min=-100000000, max=100000000)
    ])
    
    is_in_trust = BooleanField('Held in Trust?')
    
    owner_id = SelectField('Current Owner', coerce=int, validators=[Optional()])
    
    # CHANGED: Replaced TextArea with HiddenField to store the JSON string
    attributes_json = HiddenField('Attributes JSON')

    submit = SubmitField('Save Asset')