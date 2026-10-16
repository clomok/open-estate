from datetime import date

from flask_wtf import FlaskForm
from wtforms import (StringField, SelectField, FloatField, BooleanField, SubmitField,
                     TextAreaField, DateField, SelectMultipleField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from wtforms.widgets import ListWidget, CheckboxInput

from src.holding_types import parse_field, FREQUENCIES
from src.models import (PERSON_ROLES, ENTITY_KINDS, ENTITY_KIND_LABELS,
                        DESIGNATION_KINDS, DESIGNATION_KIND_LABELS)
from src.money import to_cents, cents_to_input


class MoneyField(StringField):
    """Typed in dollars ("1,250.50"), held as int cents in .data."""

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        return cents_to_input(self.data)

    def process_formdata(self, valuelist):
        if valuelist:
            try:
                self.data = to_cents(valuelist[0])
            except ValueError:
                self.data = None
                raise ValueError("Enter an amount, e.g. 1250 or 1,250.50")


def _not_negative(form, field):
    if field.data is not None and field.data < 0:
        raise ValidationError("Enter the amount as a positive number.")


# --- Holdings --------------------------------------------------------------

class HoldingForm(FlaskForm):
    """The columns every holding shares. Per-type detail fields are added by
    build_holding_form() from the registry, prefixed `attr_`."""
    name = StringField('Name / title', validators=[DataRequired(), Length(max=150)])
    value = MoneyField('Value', validators=[Optional(), _not_negative])
    entity_id = SelectField('Held by', coerce=int, validators=[Optional()])
    owner_id = SelectField('Individual owner', coerce=int, validators=[Optional()])
    ownership_pct = FloatField('Ownership %', validators=[Optional(), NumberRange(0, 100)])
    secured_by_id = SelectField('Secured by', coerce=int, validators=[Optional()])
    notes = TextAreaField('Notes')
    submit = SubmitField('Save')


def _attr_validator(reg_field):
    def check(form, field):
        try:
            parse_field(reg_field, field.data)
        except ValueError as e:
            raise ValidationError(str(e))
    return check


def build_holding_form(htype):
    """A form class for one holding type, generated from the registry."""
    attrs = {}
    for f in htype.fields:
        validators = [Optional(), _attr_validator(f)]
        kw = {"description": "Sensitive - masked on screen" if f.is_sensitive else ""}
        if f.type == "textarea":
            field = TextAreaField(f.label, validators=validators, **kw)
        elif f.type == "select":
            field = SelectField(f.label, choices=[("", "—")] + list(f.choices),
                                validators=validators, **kw)
        elif f.type == "date":
            field = StringField(f.label, validators=validators,
                                render_kw={"type": "date"}, **kw)
        elif f.type in ("number", "percent", "money"):
            hint = {"money": "$", "percent": "%", "number": ""}[f.type]
            field = StringField(f.label, validators=validators,
                                render_kw={"inputmode": "decimal", "data-unit": hint}, **kw)
        else:
            field = StringField(f.label, validators=validators, **kw)
        attrs["attr_" + f.name] = field
    if htype.custom:
        attrs["custom_type_label"] = StringField(
            'What kind of thing is this?', validators=[DataRequired(), Length(max=100)],
            render_kw={"placeholder": "e.g. Boat slip lease, Promissory note"})
    return type(f"{htype.side}_{htype.code}_Form", (HoldingForm,), attrs)


class ValuationForm(FlaskForm):
    date = DateField('Date of valuation', default=date.today, validators=[DataRequired()])
    value = MoneyField('New value ($)', validators=[DataRequired(), _not_negative])
    source = StringField('Source (e.g. Zillow, KBB, Statement)', validators=[Length(max=100)])
    notes = TextAreaField('Notes')
    submit = SubmitField('Add valuation')


class DesignationForm(FlaskForm):
    person_id = SelectField('Beneficiary', coerce=int, validators=[DataRequired()])
    percentage = FloatField('Share %', validators=[DataRequired(), NumberRange(0.01, 100)])
    kind = SelectField('Designated by', choices=[(k, DESIGNATION_KIND_LABELS[k])
                                                for k in DESIGNATION_KINDS])
    notes = StringField('Notes', validators=[Optional(), Length(max=500)])
    submit = SubmitField('Save share')


# --- People ----------------------------------------------------------------

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class PersonForm(FlaskForm):
    name = StringField('Name / organisation', validators=[DataRequired(), Length(max=100)])
    kind = SelectField('This is', choices=[("individual", "A person"),
                                          ("organisation", "An organisation / firm")])
    roles = MultiCheckboxField('Roles', choices=PERSON_ROLES,
                               validators=[DataRequired(message="Pick at least one role.")])
    email = StringField('Email', validators=[Optional(), Length(max=120)])
    phone = StringField('Phone', validators=[Optional(), Length(max=20)])
    address = TextAreaField('Physical address', validators=[Optional()])
    notes = TextAreaField('Notes / instructions', validators=[Optional()])
    submit = SubmitField('Save contact')


# --- Sub-items -------------------------------------------------------------

class StructureForm(FlaskForm):
    name = StringField('Structure name', validators=[DataRequired()], render_kw={"placeholder": "e.g. North Garden Shed"})
    structure_type = StringField('Type', render_kw={"placeholder": "e.g. Outbuilding, Deck, Pool"})
    description = TextAreaField('Description')
    date_last_maintained = DateField('Last maintained', validators=[Optional()])
    notes = TextAreaField('Maintenance notes')
    submit = SubmitField('Save structure')


class LocationPointForm(FlaskForm):
    label = StringField('Label', validators=[DataRequired()], render_kw={"placeholder": "e.g. Septic Tank Lid"})
    description = TextAreaField('Description', render_kw={"placeholder": "e.g. Buried 6 inches deep..."})
    latitude = FloatField('Latitude', validators=[DataRequired()])
    longitude = FloatField('Longitude', validators=[DataRequired()])
    submit = SubmitField('Save pin')


class RecurringBillForm(FlaskForm):
    name = StringField('Bill name', validators=[DataRequired()], render_kw={"placeholder": "e.g. Property Tax, Insurance"})
    payee = StringField('Payee', render_kw={"placeholder": "e.g. County Treasurer"})
    account_number = StringField('Account number')
    amount_cents = MoneyField('Est. amount ($)', validators=[Optional(), _not_negative])
    frequency = SelectField('Frequency', choices=FREQUENCIES)
    is_autopay = BooleanField('Autopay enabled?')
    next_due_date = DateField('Next due date', validators=[Optional()])
    submit = SubmitField('Save bill')


class HoldingVendorForm(FlaskForm):
    person_id = SelectField('Select contact', coerce=int, validators=[DataRequired()])
    role = StringField('Service role', validators=[DataRequired()], render_kw={"placeholder": "e.g. Pool Cleaner, Mechanic, Advisor"})
    notes = TextAreaField('Notes', render_kw={"placeholder": "Account #, gate code for them..."})
    submit = SubmitField('Assign')


# --- The trust and its add-on entities -------------------------------------

class TrustProfileForm(FlaskForm):
    """Edits the root entity - the trust every dataset is built around."""
    name = StringField('Official trust name', validators=[DataRequired()])
    date_established = DateField('Date established', validators=[Optional()])

    # Sensitive
    date_death_estimated = DateField('Actuarial horizon / estimate', validators=[Optional()],
                                     description="Used for planning projections only.")
    date_death_actual = DateField('Actual date of passing', validators=[Optional()],
                                  description="Setting this enters Transition Mode.")

    # Review
    review_frequency = SelectField('Review frequency', choices=[('Annual', 'Annual'), ('Quarterly', 'Quarterly')])
    next_review_date = DateField('Next review scheduled', validators=[Optional()])

    notes = TextAreaField('Trust notes', render_kw={"rows": 5})
    submit = SubmitField('Save trust details')


class EntityForm(FlaskForm):
    """An add-on under the trust: an LLC, a corporation, an IRA, a person's
    own name for things held outside the trust."""
    kind = SelectField('Kind', choices=[(k, ENTITY_KIND_LABELS[k]) for k in ENTITY_KINDS])
    name = StringField('Name', validators=[DataRequired(), Length(max=200)])
    person_id = SelectField('Person (for things held personally)', coerce=int,
                            validators=[Optional()])
    date_established = DateField('Date established / opened', validators=[Optional()])
    notes = TextAreaField('Notes')
    submit = SubmitField('Save')
