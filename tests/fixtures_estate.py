"""Shared estate fixture: one row of every model, a holding on each side, and
beneficiary shares.

Lives apart from the tests so the same data can be driven through other
builds of the export/import services as a control.
"""

from datetime import date

from src.models import (
    BeneficiaryDesignation,
    Entity,
    Holding,
    HoldingVendor,
    LocationPoint,
    Milestone,
    Person,
    PersonRole,
    PropertyStructure,
    RecurringBill,
    Task,
    Valuation,
)
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES


def _populate(db):
    """One row of every kind, with a value in every column worth checking."""
    trustor = Person(id=1, name="Tony Example", email="tony@example.com",
                     phone="555-0100", attributes={"relationship": "Father"},
                     last_verified=date(2026, 1, 2))
    heir = Person(id=2, name="John Example", email="john@example.com", phone="555-0101",
                  attributes={})
    plumber = Person(id=3, name="Pat Pipewrench Inc.", kind="organisation",
                     email="pat@example.com", phone="555-0102", attributes={})
    db.session.add_all([trustor, heir, plumber])
    db.session.flush()
    db.session.add_all([
        PersonRole(id=1, person_id=1, role="Trustor"),
        PersonRole(id=2, person_id=1, role="Trustee"),      # two roles, one person
        PersonRole(id=3, person_id=2, role="Beneficiary"),
        PersonRole(id=4, person_id=3, role="Vendor"),
    ])

    root = Entity(id=1, kind="trust", name="The Example Family Trust", is_root=True,
                  date_established=date(2014, 2, 9), date_death_estimated=date(2048, 1, 1),
                  review_frequency="Annual", next_review_date=date(2027, 2, 9),
                  notes="Reviewed by counsel")
    llc = Entity(id=2, kind="llc", name="Example Rentals LLC", is_root=False, parent_id=1,
                 date_established=date(2019, 3, 1))
    db.session.add_all([root, llc])
    db.session.flush()

    house = Holding(id=10, side="asset", type_code="real_estate", name="Family Home",
                    entity_id=None, owner_id=1, value_cents=75000000,
                    attributes={"address": "1 Example Way", "purchase_price": 40000050})
    car = Holding(id=11, side="asset", type_code="vehicle", name="1969 Coupe",
                  entity_id=2, owner_id=1, value_cents=4200000,
                  attributes={"vin": "EXAMPLE123"}, last_verified=date(2025, 12, 1))
    mortgage = Holding(id=12, side="liability", type_code="mortgage", name="Home Mortgage",
                       value_cents=25000000, secured_by_id=10,
                       attributes={"lender": "Example Bank", "interest_rate": 3.5})
    stake = Holding(id=13, side="equity", type_code="llc_units", name="Rentals LLC units",
                    value_cents=12000000, ownership_pct=50.0,
                    attributes={"company": "Example Rentals LLC", "units_held": 500})
    boat = Holding(id=14, side="asset", type_code="custom", name="Marina slip",
                   value_cents=500000,
                   attributes={"type_label": "Boat slip lease",
                               "fields": [{"name": "Slip", "value": "B-14"}]})
    db.session.add_all([house, car, stake, boat])
    db.session.flush()
    db.session.add(mortgage)
    db.session.flush()

    db.session.add_all([
        BeneficiaryDesignation(id=1, holding_id=10, person_id=2, percentage=65.0,
                               kind="trust_schedule", notes="Per schedule A"),
        BeneficiaryDesignation(id=2, holding_id=10, person_id=1, percentage=35.0,
                               kind="trust_schedule"),
        Valuation(id=20, holding_id=10, date=date(2025, 4, 1), value_cents=74000000,
                  source="Zillow", notes="Pre-renovation"),
        Task(id=30, title="Retitle the coupe", status="Pending",
             due_date=date(2026, 3, 15), is_recurring=False, holding_id=11),
        Task(id=31, title="Annual trust review", status="Done",
             due_date=date(2026, 1, 5), is_recurring=True, holding_id=None),
        Milestone(id=40, title="Trust funded", date_event=date(2024, 6, 1),
                  description="All assets retitled", is_completed=True),
        PropertyStructure(id=50, holding_id=10, name="North Garden Shed",
                          structure_type="Outbuilding", description="Tools",
                          date_built=date(2011, 5, 2),
                          date_last_maintained=date(2025, 8, 14), notes="Repaint 2027"),
        LocationPoint(id=60, holding_id=10, label="Septic Tank Lid",
                      latitude=33.5427, longitude=-117.6631,
                      description="Under the fake rock"),
        RecurringBill(id=70, holding_id=10, name="County Property Tax",
                      payee="County Treasurer", account_number="ACCT-9911",
                      amount_cents=820050, frequency="Annual",
                      is_autopay=False, next_due_date=date(2026, 11, 1),
                      notes="Two installments"),
        RecurringBill(id=71, holding_id=11, name="Classic car insurance",
                      payee="Example Mutual", amount_cents=60000, frequency="Annual"),
        HoldingVendor(id=80, holding_id=10, person_id=3, role="Plumber",
                      notes="Knows where the main shutoff is"),
    ])
    db.session.commit()


def _wipe(db):
    for _, table in BACKUP_TABLES:
        db.session.execute(table.delete())
    for _, model in reversed(BACKUP_MODELS):
        db.session.query(model).delete()
    db.session.commit()
