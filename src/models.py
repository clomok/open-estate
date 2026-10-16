"""Schema v3 - the ledger foundation.

The shape, in one breath: every dataset has exactly one root `Entity`, the
trust. Everything the estate has or owes is a `Holding` on one of three sides
(asset, liability, equity); a holding with no entity sits in the trust, and
other entities (an LLC, a corporation, a retirement account, a person's own
name) are optional add-ons under the root. People carry any number of roles,
and who inherits what share of which holding is a `BeneficiaryDesignation`.

Money is Integer cents. Dates are Date. Every table carries created_at,
updated_at and last_verified, because a binder's main failure is going stale.

Changing this file means writing an Alembic migration AND updating
src/services/backup_schema.py - see AI_INSTRUCTIONS.md section 4.5.
"""

from datetime import date, datetime, timezone

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func, text

from src.extensions import db
from src.holding_types import SIDES, get_type, SIDE_META

ENTITY_KINDS = ("trust", "corporation", "llc", "retirement_account", "individual")
ENTITY_KIND_LABELS = {
    "trust": "Trust", "corporation": "Corporation", "llc": "LLC",
    "retirement_account": "Retirement account", "individual": "Held personally",
}
PERSON_KINDS = ("individual", "organisation")
DESIGNATION_KINDS = ("trust_schedule", "account_tod", "will")
DESIGNATION_KIND_LABELS = {
    "trust_schedule": "Trust schedule", "account_tod": "Account TOD / POD",
    "will": "Will",
}

# Roles a person can hold. "Family" roles put them in the top half of the
# contacts page; the rest are the professional team.
PERSON_ROLES = [
    ("Trustor", "Trustor (grantor)"), ("Trustee", "Trustee"),
    ("SuccessorTrustee", "Successor trustee"), ("Beneficiary", "Beneficiary"),
    ("Executor", "Executor"), ("Attorney", "Attorney"),
    ("Financial Advisor", "Financial advisor"), ("Accountant", "Accountant / CPA"),
    ("Funeral Director", "Funeral service"), ("Medical", "Doctor / medical"),
    ("Insurance", "Insurance agent"), ("Vendor", "Vendor / service provider"),
    ("Other", "Other"),
]
FAMILY_ROLES = {"Trustor", "Trustee", "SuccessorTrustee", "Beneficiary", "Executor"}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _in(column, values):
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AuditMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow,
                           server_default=func.current_timestamp())
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow,
                           server_default=func.current_timestamp())
    # Set by a person pressing "mark verified", never by an edit: an edit
    # says something changed, verification says someone checked it is true.
    last_verified = db.Column(db.Date, nullable=True)

    def mark_verified(self, on=None):
        self.last_verified = on or date.today()


# --- People ----------------------------------------------------------------

class Person(AuditMixin, db.Model):
    __table_args__ = (CheckConstraint(_in("kind", PERSON_KINDS), name="ck_person_kind"),)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="individual",
                     server_default="individual")
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    attributes = db.Column(db.JSON, default=dict)

    roles = db.relationship("PersonRole", backref="person", lazy=True,
                            cascade="all, delete-orphan", order_by="PersonRole.id")
    holdings_owned = db.relationship("Holding", backref="owner", lazy=True)
    service_jobs = db.relationship("HoldingVendor", backref="provider", lazy=True)
    designations = db.relationship("BeneficiaryDesignation", backref="person", lazy=True)

    @property
    def role_codes(self):
        return [r.role for r in self.roles]

    @property
    def role_labels(self):
        labels = dict(PERSON_ROLES)
        return [labels.get(r.role, r.role) for r in self.roles]

    def has_role(self, *codes):
        return any(r.role in codes for r in self.roles)

    def set_roles(self, codes):
        wanted = list(dict.fromkeys(c for c in codes if c))
        keep = [r for r in self.roles if r.role in wanted]
        have = {r.role for r in keep}
        self.roles = keep + [PersonRole(role=c) for c in wanted if c not in have]


class PersonRole(AuditMixin, db.Model):
    __tablename__ = "person_role"
    __table_args__ = (UniqueConstraint("person_id", "role", name="uq_person_role"),)

    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="CASCADE"),
                          nullable=False)
    role = db.Column(db.String(50), nullable=False)


# --- Entities: the trust, and what hangs off it ----------------------------

class Entity(AuditMixin, db.Model):
    __table_args__ = (
        CheckConstraint(_in("kind", ENTITY_KINDS), name="ck_entity_kind"),
        CheckConstraint("is_root = 0 OR kind = 'trust'", name="ck_entity_root_is_trust"),
        CheckConstraint("(is_root = 1 AND parent_id IS NULL) OR "
                        "(is_root = 0 AND parent_id IS NOT NULL)",
                        name="ck_entity_root_has_no_parent"),
        # Exactly one root per dataset: at most one row may have is_root = 1.
        Index("uq_entity_one_root", "is_root", unique=True,
              sqlite_where=text("is_root = 1")),
    )

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    is_root = db.Column(db.Boolean, nullable=False, default=False, server_default="0")
    parent_id = db.Column(db.Integer, db.ForeignKey("entity.id"), nullable=True)
    # For kind `individual`: whose own name the holdings are in.
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=True)

    date_established = db.Column(db.Date, nullable=True)
    # Transition planning (carried over from the old TrustProfile)
    date_death_estimated = db.Column(db.Date, nullable=True)
    date_death_actual = db.Column(db.Date, nullable=True)
    review_frequency = db.Column(db.String(50), default="Annual")
    next_review_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)
    attributes = db.Column(db.JSON, default=dict)

    parent = db.relationship("Entity", remote_side=[id], backref="children")
    person = db.relationship("Person")
    holdings = db.relationship("Holding", backref="entity", lazy=True)

    @property
    def kind_label(self):
        return ENTITY_KIND_LABELS.get(self.kind, self.kind)


# --- The ledger ------------------------------------------------------------

class Holding(AuditMixin, db.Model):
    __table_args__ = (
        CheckConstraint(_in("side", SIDES), name="ck_holding_side"),
        CheckConstraint("value_cents >= 0", name="ck_holding_value_positive"),
        CheckConstraint("ownership_pct IS NULL OR (ownership_pct >= 0 AND ownership_pct <= 100)",
                        name="ck_holding_ownership_pct"),
    )

    id = db.Column(db.Integer, primary_key=True)
    side = db.Column(db.String(10), nullable=False)
    type_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    # NULL = held in the trust (the root entity). A non-null value is an add-on.
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id"), nullable=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=True)
    # Always positive; the side gives the sign. Net worth = assets - liabilities.
    value_cents = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    attributes = db.Column(db.JSON, default=dict)
    ownership_pct = db.Column(db.Float, nullable=True)          # equity only
    secured_by_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="SET NULL"),
                              nullable=True)                    # liability only
    notes = db.Column(db.Text)

    secured_by = db.relationship("Holding", remote_side=[id], backref="secures")
    valuations = db.relationship("Valuation", backref="holding", lazy=True,
                                 cascade="all, delete-orphan",
                                 order_by="desc(Valuation.date)")
    structures = db.relationship("PropertyStructure", backref="holding", lazy=True,
                                 cascade="all, delete-orphan")
    location_points = db.relationship("LocationPoint", backref="holding", lazy=True,
                                      cascade="all, delete-orphan")
    bills = db.relationship("RecurringBill", backref="holding", lazy=True,
                            cascade="all, delete-orphan")
    vendors = db.relationship("HoldingVendor", backref="holding", lazy=True,
                              cascade="all, delete-orphan")
    beneficiary_designations = db.relationship(
        "BeneficiaryDesignation", backref="holding", lazy=True,
        cascade="all, delete-orphan", order_by="BeneficiaryDesignation.id")

    @property
    def htype(self):
        return get_type(self.side, self.type_code)

    @property
    def type_label(self):
        t = self.htype
        if t and t.custom:
            return (self.attributes or {}).get("type_label") or "Custom"
        return t.label if t else self.type_code

    @property
    def icon(self):
        t = self.htype
        return t.icon if t else "📦"

    @property
    def side_meta(self):
        return SIDE_META[self.side]

    @property
    def in_trust(self):
        return self.entity_id is None

    @property
    def signed_cents(self):
        """Contribution to net worth: assets +, liabilities -, equity 0.

        Equity is reported beside net worth, not inside it - see the
        2026-10-15 decision in the project record (double counting when the
        entity a stake is in is itself modelled)."""
        if self.side == "asset":
            return self.value_cents
        if self.side == "liability":
            return -self.value_cents
        return 0

    def share_totals(self):
        """{designation kind: total percentage} - each kind should reach 100."""
        totals = {}
        for d in self.beneficiary_designations:
            totals[d.kind] = round(totals.get(d.kind, 0) + d.percentage, 4)
        return totals


class Valuation(AuditMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    value_cents = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(100))      # e.g. "Zillow", "Statement", "KBB"
    notes = db.Column(db.Text)


class BeneficiaryDesignation(AuditMixin, db.Model):
    __tablename__ = "beneficiary_designation"
    __table_args__ = (
        UniqueConstraint("holding_id", "person_id", "kind", name="uq_designation"),
        CheckConstraint(_in("kind", DESIGNATION_KINDS), name="ck_designation_kind"),
        CheckConstraint("percentage > 0 AND percentage <= 100", name="ck_designation_pct"),
    )

    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    # No cascade from person: deleting someone must not silently erase who
    # inherits what. The delete is refused until their shares are reassigned.
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    percentage = db.Column(db.Float, nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="trust_schedule")
    notes = db.Column(db.Text)

    @property
    def kind_label(self):
        return DESIGNATION_KIND_LABELS.get(self.kind, self.kind)


# --- Sub-items (offered on every holding) ----------------------------------

class PropertyStructure(AuditMixin, db.Model):
    """Accommodations: sheds, pools, decks, garages."""
    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    name = db.Column(db.String(100), nullable=False)
    structure_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    date_built = db.Column(db.Date, nullable=True)
    date_last_maintained = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)


class LocationPoint(AuditMixin, db.Model):
    """A pin: where a specific thing is (septic lid, safe, water shutoff)."""
    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    label = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)


class RecurringBill(AuditMixin, db.Model):
    """A cost of holding something: tax, insurance, utilities, HOA, fees."""
    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    name = db.Column(db.String(100), nullable=False)
    payee = db.Column(db.String(100))
    account_number = db.Column(db.String(100))
    amount_cents = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    frequency = db.Column(db.String(50))
    is_autopay = db.Column(db.Boolean, default=False)
    next_due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)


class HoldingVendor(AuditMixin, db.Model):
    """A contact's role on one specific holding (pool cleaner, mechanic, advisor)."""
    __tablename__ = "holding_vendor"

    id = db.Column(db.Integer, primary_key=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="CASCADE"),
                           nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id"), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.Text)


# --- The timeline: what has to happen, and when ----------------------------

EVENT_KINDS = ("task", "deadline", "renewal", "review", "milestone", "memory")
EVENT_KIND_LABELS = {
    "task": "Task", "deadline": "Deadline", "renewal": "Renewal",
    "review": "Review", "milestone": "Milestone", "memory": "Memory",
}
EVENT_KIND_ICONS = {
    "task": "📌", "deadline": "⏰", "renewal": "🔁", "review": "🔍",
    "milestone": "🚩", "memory": "📷",
}
# now = keeping the binder true while everyone is here; planning = estate
# planning work; transition = the weeks after a death; administration = the
# long tail of settling the trust.
EVENT_PHASES = ("now", "planning", "transition", "administration")
EVENT_PHASE_LABELS = {
    "now": "Now", "planning": "Planning", "transition": "Transition",
    "administration": "Administration",
}
REPEAT_UNITS = ("day", "week", "month", "year")


class Event(AuditMixin, db.Model):
    """One thing on the timeline. Replaces the v3 `task` and `milestone`.

    `source` is set when the row stands for something the app derives (a
    bill falling due, a holding nobody has verified): the derived feed skips
    any source that already has a row, so touching a derived item - done,
    snooze, a note - turns it into exactly one stored event. See
    src/services/feeds.py."""
    __table_args__ = (
        CheckConstraint(_in("kind", EVENT_KINDS), name="ck_event_kind"),
        CheckConstraint(_in("phase", EVENT_PHASES), name="ck_event_phase"),
        CheckConstraint("repeat_unit IS NULL OR " + _in("repeat_unit", REPEAT_UNITS),
                        name="ck_event_repeat_unit"),
        CheckConstraint("repeat_every IS NULL OR repeat_every > 0",
                        name="ck_event_repeat_every"),
        Index("uq_event_source", "source", unique=True,
              sqlite_where=text("source IS NOT NULL")),
        Index("ix_event_open_date", "done_at", "date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20), nullable=False, default="task", server_default="task")
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.Date, nullable=True)          # undated = "whenever, but do it"
    done_at = db.Column(db.Date, nullable=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="SET NULL"),
                            nullable=True)
    phase = db.Column(db.String(20), nullable=False, default="now", server_default="now")
    description = db.Column(db.Text)
    # What it is about (all optional). Deleting the record keeps the event.
    holding_id = db.Column(db.Integer, db.ForeignKey("holding.id", ondelete="SET NULL"),
                           nullable=True)
    entity_id = db.Column(db.Integer, db.ForeignKey("entity.id", ondelete="SET NULL"),
                          nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey("person.id", ondelete="SET NULL"),
                          nullable=True)
    source = db.Column(db.String(120), nullable=True)
    repeat_every = db.Column(db.Integer, nullable=True)
    repeat_unit = db.Column(db.String(10), nullable=True)

    assignee = db.relationship("Person", foreign_keys=[assignee_id],
                               backref=db.backref("assigned_events", lazy=True))
    person = db.relationship("Person", foreign_keys=[person_id],
                             backref=db.backref("events", lazy=True))
    holding = db.relationship("Holding", backref=db.backref(
        "events", lazy=True, order_by="Event.date"))
    entity = db.relationship("Entity", backref=db.backref("events", lazy=True))

    @property
    def is_done(self):
        return self.done_at is not None

    @property
    def kind_label(self):
        return EVENT_KIND_LABELS.get(self.kind, self.kind)

    @property
    def icon(self):
        return EVENT_KIND_ICONS.get(self.kind, "•")

    @property
    def phase_label(self):
        return EVENT_PHASE_LABELS.get(self.phase, self.phase)

    @property
    def repeats(self):
        return bool(self.repeat_every and self.repeat_unit)


class Playbook(AuditMixin, db.Model):
    """A list of steps, each a number of days after a trigger date. Running
    it on a date makes one event per step. The death-of-trustor playbook is
    shipped as an editable default (src/services/default_playbook.py)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    # What sets it off. "death_of_trustor" is offered when the trust's
    # date_death_actual is filled in; NULL = run by hand only.
    trigger = db.Column(db.String(50), nullable=True)

    steps = db.relationship("PlaybookStep", backref="playbook", lazy=True,
                            cascade="all, delete-orphan",
                            order_by="(PlaybookStep.offset_days, PlaybookStep.position)")


class PlaybookStep(AuditMixin, db.Model):
    __tablename__ = "playbook_step"

    id = db.Column(db.Integer, primary_key=True)
    playbook_id = db.Column(db.Integer, db.ForeignKey("playbook.id", ondelete="CASCADE"),
                            nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    offset_days = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    title = db.Column(db.String(200), nullable=False)
    # A role code from PERSON_ROLES; the run assigns the first person holding it.
    who_role = db.Column(db.String(50), nullable=True)
    instructions = db.Column(db.Text)
    # Free text until Phase C adds documents: what to find before doing this.
    document_type = db.Column(db.String(100), nullable=True)
    kind = db.Column(db.String(20), nullable=False, default="task", server_default="task")
