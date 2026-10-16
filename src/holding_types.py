"""The one list of what the ledger can hold.

Every holding has a `side` (asset, liability, equity) and a `type_code`. This
registry says, for each (side, type), what it is called, its icon, and which
detail fields it carries - each with a `type` (how it is parsed, stored and
shown) and a `sensitivity` (whether the screen masks it until asked).

Forms, the detail page, the add-item picker, the timeline icons and the save
validation all read this file. Before it existed there were four separate
type lists that disagreed with each other.

Adding a built-in type is one entry below. Adding a type nobody anticipated
needs no code at all: every side has `custom`, whose fields the user names.
"""

from dataclasses import dataclass, field as dc_field
from datetime import date

from src.money import to_cents, format_cents, cents_to_input

SIDES = ("asset", "liability", "equity")

SIDE_META = {
    "asset": {
        "label": "Assets", "singular": "Asset", "icon": "💰",
        "value_label": "Current value",
    },
    "liability": {
        "label": "Liabilities", "singular": "Liability", "icon": "📉",
        "value_label": "Outstanding balance",
    },
    "equity": {
        "label": "Equity", "singular": "Equity stake", "icon": "📊",
        "value_label": "Value of the stake",
    },
}

FIELD_TYPES = ("text", "textarea", "money", "date", "number", "percent", "select")
SENSITIVITIES = ("normal", "sensitive")

FREQUENCIES = [("Monthly", "Monthly"), ("Quarterly", "Quarterly"),
               ("Annual", "Annual"), ("Other", "Other")]


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    type: str = "text"
    sensitivity: str = "normal"
    choices: tuple = ()
    help: str = ""

    def __post_init__(self):
        assert self.type in FIELD_TYPES, self.type
        assert self.sensitivity in SENSITIVITIES, self.sensitivity

    @property
    def is_sensitive(self):
        return self.sensitivity == "sensitive"


@dataclass(frozen=True)
class HoldingType:
    side: str
    code: str
    label: str
    icon: str
    fields: tuple = dc_field(default_factory=tuple)
    custom: bool = False

    def field(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        return None


def _f(*args, **kwargs):
    return Field(*args, **kwargs)


_ACCOUNT = _f("account_number", "Account number", sensitivity="sensitive")
_PURCHASE = (_f("purchase_date", "Date purchased", "date"),
             _f("purchase_price", "Purchase price", "money"))
_PERSONAL_ITEM = (_f("description", "Description", "textarea"),
                  _f("location", "Where it is kept", sensitivity="sensitive"),
                  _f("appraisal_date", "Date appraised", "date"),
                  _f("appraiser_info", "Appraiser"))
_LENDER = (_f("lender", "Lender / creditor"), _ACCOUNT,
           _f("interest_rate", "Interest rate", "percent"),
           _f("monthly_payment", "Monthly payment", "money"),
           _f("payment_due_day", "Payment due (day of month)", "number"))

_TYPES = [
    # --- Assets -----------------------------------------------------------
    HoldingType("asset", "real_estate", "Real estate", "🏠", (
        _f("address", "Property address", "textarea"),
        _f("apn_number", "APN / parcel number"),
        *_PURCHASE)),
    HoldingType("asset", "vehicle", "Vehicle", "🚗", (
        _f("year", "Year"), _f("make", "Make"), _f("model", "Model"),
        _f("vin", "VIN", sensitivity="sensitive"),
        _f("license_plate", "License plate"),
        _f("location_keys", "Where the spare keys are", sensitivity="sensitive"),
        *_PURCHASE)),
    HoldingType("asset", "bank", "Bank account", "🏦", (
        _f("institution", "Bank / institution"),
        _f("account_type", "Account type", "select", choices=(
            ("Checking", "Checking"), ("Savings", "Savings"),
            ("CD", "Certificate of deposit"), ("MoneyMarket", "Money market"),
            ("SafeDeposit", "Safe deposit box"))),
        _ACCOUNT,
        _f("routing_number", "Routing number", sensitivity="sensitive"))),
    HoldingType("asset", "investment", "Investment account", "📈", (
        _f("institution", "Brokerage / firm"), _ACCOUNT,
        _f("advisor_name", "Advisor"), _f("advisor_contact", "Advisor phone / email"))),
    HoldingType("asset", "retirement", "Retirement account", "🏛️", (
        _f("institution", "Custodian"),
        _f("plan_type", "Plan type", "select", choices=(
            ("IRA", "Traditional IRA"), ("Roth", "Roth IRA"), ("401k", "401(k)"),
            ("403b", "403(b)"), ("Pension", "Pension"), ("Other", "Other"))),
        _ACCOUNT, _f("advisor_name", "Advisor"))),
    HoldingType("asset", "jewelry", "Jewelry / watch", "💎", _PERSONAL_ITEM),
    HoldingType("asset", "art", "Art / collectible", "🎨",
                (_f("artist", "Artist / maker"),) + _PERSONAL_ITEM),
    HoldingType("asset", "income_stream", "Income stream", "💵", (
        _f("payer", "Paid by"),
        _f("stream_type", "Kind", "select", choices=(
            ("Pension", "Pension"), ("SocialSecurity", "Social Security"),
            ("Rental", "Rental income"), ("Annuity", "Annuity"),
            ("Royalty", "Royalty"), ("Other", "Other"))),
        _f("amount_per_period", "Amount per payment", "money"),
        _f("frequency", "How often", "select", choices=tuple(FREQUENCIES)),
        _f("ends_on", "Ends on", "date"))),
    HoldingType("asset", "other", "Other asset", "📦", (
        _f("description", "Description", "textarea"),
        _f("location", "Where it is kept", sensitivity="sensitive"))),

    # --- Liabilities ------------------------------------------------------
    HoldingType("liability", "mortgage", "Mortgage", "🏘️", _LENDER + (
        _f("original_principal", "Original principal", "money"),
        _f("maturity_date", "Paid off on", "date"))),
    HoldingType("liability", "loan", "Loan", "💸", _LENDER + (
        _f("original_principal", "Original principal", "money"),
        _f("maturity_date", "Paid off on", "date"))),
    HoldingType("liability", "credit_line", "Credit line / card", "💳", _LENDER + (
        _f("credit_limit", "Credit limit", "money"),)),
    HoldingType("liability", "tax_owed", "Tax owed", "🧾", (
        _f("authority", "Owed to (IRS, state, county)"),
        _f("tax_year", "Tax year", "number"),
        _f("due_date", "Due date", "date"),
        _f("reference", "Notice / reference number"))),
    HoldingType("liability", "other", "Other liability", "📉", (
        _f("creditor", "Owed to"), _ACCOUNT,
        _f("description", "Description", "textarea"))),

    # --- Equity -----------------------------------------------------------
    HoldingType("equity", "business_shares", "Business shares", "🏢", (
        _f("company", "Company"), _f("share_class", "Share class"),
        _f("shares_held", "Shares held", "number"),
        _f("ein", "Company EIN"),
        _f("certificate_location", "Where the certificates are"))),
    HoldingType("equity", "llc_units", "LLC units", "📑", (
        _f("company", "LLC"), _f("units_held", "Units held", "number"),
        _f("ein", "LLC EIN"),
        _f("operating_agreement_location", "Where the operating agreement is"))),
    HoldingType("equity", "partnership_interest", "Partnership interest", "🤝", (
        _f("partnership", "Partnership"),
        _f("interest_type", "Interest", "select", choices=(
            ("General", "General partner"), ("Limited", "Limited partner"))),
        _f("ein", "Partnership EIN"))),
    HoldingType("equity", "co_owned_property", "Co-owned property share", "🏡", (
        _f("property", "Property", "textarea"),
        _f("co_owners", "Other owners"),
        _f("title_form", "How title is held", "select", choices=(
            ("TIC", "Tenants in common"), ("JTWROS", "Joint tenancy"),
            ("Community", "Community property"), ("Other", "Other"))))),
    HoldingType("equity", "other", "Other equity", "📊", (
        _f("stake_in", "Stake in"),
        _f("description", "Description", "textarea"))),
]

# Every side also takes a user-defined type: its label and fields are data.
for _side in SIDES:
    _TYPES.append(HoldingType(_side, "custom", "Custom…", "✳️", (), custom=True))

REGISTRY = {(t.side, t.code): t for t in _TYPES}


def get_type(side, code):
    return REGISTRY.get((side, code))


def types_for(side):
    return [t for t in _TYPES if t.side == side]


def icon_for(side, code):
    t = get_type(side, code)
    return t.icon if t else "📦"


# --- Parsing, validation, display ------------------------------------------

def parse_field(field, raw):
    """Raw input (form text, or a legacy JSON value) -> the stored value.

    Returns None for "nothing entered". Raises ValueError with a message a
    person can act on."""
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if raw == "":
            return None

    if field.type in ("text", "textarea"):
        return str(raw)
    if field.type == "money":
        return to_cents(raw)
    if field.type == "date":
        if isinstance(raw, date):
            return raw.isoformat()
        try:
            return date.fromisoformat(str(raw)[:10]).isoformat()
        except ValueError:
            raise ValueError(f"'{raw}' is not a date (use YYYY-MM-DD)")
    if field.type in ("number", "percent"):
        text = str(raw).replace(",", "").rstrip("%").strip()
        try:
            n = float(text)
        except ValueError:
            raise ValueError(f"'{raw}' is not a number")
        if field.type == "percent" and not 0 <= n <= 100:
            raise ValueError(f"{n} is not a percentage between 0 and 100")
        return int(n) if n.is_integer() else n
    if field.type == "select":
        codes = [c for c, _ in field.choices]
        if raw in codes:
            return raw
        for code, label in field.choices:      # accept the label too
            if str(raw).lower() == label.lower():
                return code
        raise ValueError(f"'{raw}' is not one of the choices")
    raise ValueError(f"unknown field type {field.type}")


def _stored_ok(field, value):
    try:
        if field.type == "money":
            return isinstance(value, int) and not isinstance(value, bool)
        if field.type in ("number", "percent"):
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return parse_field(field, value) == value
    except ValueError:
        return False


def validate_attributes(htype, attrs):
    """Return a list of problems with a holding's `attributes`; [] = valid.

    Built-in types accept only their own field names, each in its stored form.
    Custom types carry {"type_label": str, "fields": [{"name", "value"}]}."""
    attrs = attrs or {}
    if not isinstance(attrs, dict):
        return ["attributes must be an object"]
    if htype.custom:
        problems = []
        extra = set(attrs) - {"type_label", "fields"}
        if extra:
            problems.append(f"unexpected keys for a custom type: {sorted(extra)}")
        label = attrs.get("type_label")
        if not isinstance(label, str) or not label.strip():
            problems.append("a custom type needs a name")
        rows = attrs.get("fields", [])
        if not isinstance(rows, list):
            return problems + ["custom fields must be a list"]
        for row in rows:
            if (not isinstance(row, dict) or set(row) != {"name", "value"}
                    or not isinstance(row["name"], str) or not row["name"].strip()
                    or not isinstance(row["value"], str)):
                problems.append(f"custom field rows need a name and a text value: {row!r}")
        return problems

    problems = []
    for key, value in attrs.items():
        f = htype.field(key)
        if f is None:
            problems.append(f"'{key}' is not a field of {htype.label}")
        elif value is not None and not _stored_ok(f, value):
            problems.append(f"{f.label}: {value!r} is not a valid {f.type}")
    return problems


def display_value(field, value):
    """Stored value -> what the detail page prints."""
    if value is None or value == "":
        return ""
    if field.type == "money":
        return format_cents(value)
    if field.type == "percent":
        return f"{value}%"
    if field.type == "select":
        return dict(field.choices).get(value, value)
    return str(value)


def input_value(field, value):
    """Stored value -> what an edit form pre-fills."""
    if value is None:
        return ""
    if field.type == "money":
        return cents_to_input(value)
    return str(value)


def mask(value):
    """Sensitive values show only their last four characters until revealed."""
    text = str(value)
    return "••••" + text[-4:] if len(text) > 4 else "••••"
