"""Shared estate fixture: one row of every model, plus a beneficiary link.

Lives apart from the tests so the same data can be driven through an older
build of the export/import services as a control.
"""

from datetime import date, datetime

from src.models import (
    asset_beneficiaries,
    Appraisal,
    Asset,
    AssetVendor,
    LocationPoint,
    Milestone,
    Person,
    PropertyStructure,
    RecurringBill,
    Task,
    TrustProfile,
)
from src.services.backup_schema import BACKUP_MODELS


def _populate(db):
    """One row of every kind, with a value in every column worth checking."""
    trustor = Person(id=1, name="Tony Example", role="Trustor",
                     email="tony@example.com", phone="555-0100",
                     attributes={"relationship": "Father"})
    heir = Person(id=2, name="John Example", role="Beneficiary",
                  email="john@example.com", phone="555-0101", attributes={})
    plumber = Person(id=3, name="Pat Pipewrench", role="Vendor",
                     email="pat@example.com", phone="555-0102", attributes={})
    db.session.add_all([trustor, heir, plumber])

    house = Asset(id=10, name="Family Home", asset_type="real_estate",
                  is_in_trust=True, owner_id=1, value_estimated=750000.0,
                  attributes={"address": "1 Example Way"})
    car = Asset(id=11, name="1969 Coupe", asset_type="vehicle",
                is_in_trust=False, owner_id=1, value_estimated=42000.0,
                attributes={"vin": "EXAMPLE123"})
    db.session.add_all([house, car])
    db.session.flush()

    # The single most load-bearing fact in the binder: who inherits what share.
    house.beneficiaries.append(heir)
    db.session.flush()
    db.session.execute(
        asset_beneficiaries.update()
        .where(asset_beneficiaries.c.asset_id == 10)
        .where(asset_beneficiaries.c.person_id == 2)
        .values(percentage=65.0)
    )

    db.session.add_all([
        Appraisal(id=20, asset_id=10, date=date(2025, 4, 1), value=740000.0,
                  source="Zillow", notes="Pre-renovation"),
        Task(id=30, title="Retitle the coupe", status="Pending",
             due_date=datetime(2026, 3, 15, 9, 0), is_recurring=False, asset_id=11),
        Task(id=31, title="Annual trust review", status="Done",
             due_date=datetime(2026, 1, 5, 12, 30), is_recurring=True, asset_id=None),
        Milestone(id=40, title="Trust funded", date_event=datetime(2024, 6, 1, 0, 0),
                  description="All assets retitled", is_completed=True),
        PropertyStructure(id=50, asset_id=10, name="North Garden Shed",
                          structure_type="Outbuilding", description="Tools",
                          date_built=date(2011, 5, 2),
                          date_last_maintained=date(2025, 8, 14), notes="Repaint 2027"),
        LocationPoint(id=60, asset_id=10, label="Septic Tank Lid",
                      latitude=33.5427, longitude=-117.6631,
                      description="Under the fake rock"),
        RecurringBill(id=70, asset_id=10, name="County Property Tax",
                      payee="County Treasurer", account_number="ACCT-9911",
                      amount_estimated=8200.0, frequency="Annual",
                      is_autopay=False, next_due_date=date(2026, 11, 1),
                      notes="Two installments"),
        AssetVendor(id=80, asset_id=10, person_id=3, role="Plumber",
                    notes="Knows where the main shutoff is"),
        TrustProfile(id=1, name="The Example Family Trust",
                     date_established=date(2014, 2, 9),
                     date_death_estimated=date(2048, 1, 1),
                     date_death_actual=None, review_frequency="Annual",
                     next_review_date=date(2027, 2, 9), notes="Reviewed by counsel"),
    ])
    db.session.commit()


def _wipe(db):
    db.session.execute(asset_beneficiaries.delete())
    for _, model in reversed(BACKUP_MODELS):
        db.session.query(model).delete()
    db.session.commit()
