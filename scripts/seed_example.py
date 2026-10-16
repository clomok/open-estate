"""Load the fake demo estate ("John & Jane Doe") into an EMPTIED database.

Refused on a DATASET_PROTECTED=1 dataset by the Makefile and ops.ps1 before
this file ever runs. It does not drop or recreate tables: the schema belongs
to the migrations, so it upgrades to head, deletes every row, and inserts.
"""

import sys
import os
from datetime import date, timedelta

# Add project root to path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask_migrate import upgrade

from app import create_app
from src.extensions import db
from src.models import (Person, Entity, Holding, Valuation, BeneficiaryDesignation,
                        PropertyStructure, LocationPoint, RecurringBill, HoldingVendor, Event)
from src.services import default_playbook
from src.services.backup_schema import BACKUP_MODELS
from src.services.estate import get_root_entity

MIGRATIONS = os.path.join(os.path.dirname(__file__), '..', 'migrations')

app = create_app()


def cents(dollars):
    return int(round(dollars * 100))


def history(holding, *points):
    """points: (date, dollars, source[, notes]) - the newest sets the value."""
    for p in points:
        db.session.add(Valuation(holding_id=holding.id, date=p[0], value_cents=cents(p[1]),
                                 source=p[2], notes=p[3] if len(p) > 3 else None))
    holding.value_cents = cents(max(points, key=lambda p: p[0])[1])


def holding(**kw):
    h = Holding(**kw)
    db.session.add(h)
    db.session.flush()
    return h


def person(name, roles, **kw):
    p = Person(name=name, **kw)
    p.set_roles(roles)
    db.session.add(p)
    return p


def seed_generalized_data():
    with app.app_context():
        print("--- [EXAMPLE] Bringing the schema to head ---")
        upgrade(directory=MIGRATIONS)

        print("--- [EXAMPLE] Clearing every row ---")
        for _, model in reversed(BACKUP_MODELS):
            db.session.query(model).delete()
        db.session.commit()
        today = date.today()

        print("--- [EXAMPLE] The trust ---")
        root = get_root_entity()
        root.name = "The Doe Family Trust"
        root.date_established = date(2012, 4, 18)
        root.review_frequency = "Annual"
        root.next_review_date = date(today.year + 1, 4, 18)
        root.notes = "Revocable living trust. Original signed copy is in the fire safe."

        print("--- [EXAMPLE] People ---")
        john = person("John Doe", ["Trustor", "Trustee"], email="john@example.com", phone="555-0100")
        jane = person("Jane Doe", ["Trustor", "Trustee"], email="jane@example.com", phone="555-0101")
        junior = person("Junior Doe", ["Beneficiary", "SuccessorTrustee"], email="junior@example.com")
        sis = person("Sally Doe", ["Beneficiary"])
        gardener = person("Green Thumb Landscaping", ["Vendor"], kind="organisation", phone="555-0199")
        attorney = person("Example & Partners LLP", ["Attorney"], kind="organisation",
                          email="office@example.com", phone="555-0150")
        mechanic = person("Main Street Garage", ["Vendor"], kind="organisation", phone="555-0177")
        db.session.flush()

        print("--- [EXAMPLE] Entities attached to the trust ---")
        john_personal = Entity(kind="individual", name="John Doe (personally held)",
                               is_root=False, parent_id=root.id, person_id=john.id)
        llc = Entity(kind="llc", name="Doe Rentals LLC", is_root=False, parent_id=root.id,
                     date_established=date(2018, 9, 1), notes="EIN 00-0000000 (example)")
        ira = Entity(kind="retirement_account", name="Jane's IRA", is_root=False, parent_id=root.id,
                     person_id=None, notes="Passes by beneficiary form, not by the trust.")
        db.session.add_all([john_personal, llc, ira])
        db.session.flush()

        print("--- [EXAMPLE] Assets ---")
        house = holding(side="asset", type_code="real_estate", name="Sample Family Home",
                        attributes={"address": "123 Demo Lane, Metropolis",
                                    "apn_number": "000-000-00",
                                    "purchase_date": "2010-01-01", "purchase_price": cents(400000)})
        history(house,
                (date(2010, 1, 1), 400000, "Purchase", "Original purchase price"),
                (date(2015, 6, 15), 475000, "Refi Appraisal", "Renovations complete"),
                (date(2018, 1, 1), 525000, "Tax Assessment"),
                (date(2020, 1, 1), 550000, "Refi Appraisal"),
                (date(2023, 1, 1), 580000, "Zillow"),
                (today, 600000, "Zillow", "Current estimate"))
        db.session.add_all([
            PropertyStructure(holding_id=house.id, name="North Garden Shed", structure_type="Outbuilding",
                              description="Prefab shed on concrete pad. Lawnmower and tools.",
                              date_last_maintained=date(2024, 5, 1)),
            LocationPoint(holding_id=house.id, label="Main Water Shutoff", latitude=32.715736,
                          longitude=-117.161087, description="Front flowerbed, under the large fake rock."),
            RecurringBill(holding_id=house.id, name="City Water", payee="Metro Water Dept",
                          account_number="9988-7766-55", amount_cents=cents(85), frequency="Monthly",
                          is_autopay=True, next_due_date=today + timedelta(days=1)),
            RecurringBill(holding_id=house.id, name="Property Tax", payee="County Treasurer",
                          amount_cents=cents(6500), frequency="Annual",
                          next_due_date=date(today.year if today.month < 11 else today.year + 1, 11, 1)),
            HoldingVendor(holding_id=house.id, person_id=gardener.id, role="Gardener / Landscaper",
                          notes="Comes every Tuesday morning. Gate code: 1234."),
            BeneficiaryDesignation(holding_id=house.id, person_id=junior.id, percentage=50,
                                   kind="trust_schedule", notes="Schedule A, item 1"),
            BeneficiaryDesignation(holding_id=house.id, person_id=sis.id, percentage=50,
                                   kind="trust_schedule"),
        ])

        truck = holding(side="asset", type_code="vehicle", name="2020 Ford F-150",
                        entity_id=john_personal.id, owner_id=john.id,
                        attributes={"year": "2020", "make": "Ford", "model": "F-150",
                                    "vin": "1FTEW1E45LKD12345", "license_plate": "TRK-999",
                                    "location_keys": "Hook inside the pantry door",
                                    "purchase_date": "2020-05-15", "purchase_price": cents(45000)})
        history(truck,
                (date(2020, 5, 15), 45000, "Purchase", "Dealer invoice"),
                (date(2021, 5, 15), 41000, "KBB"),
                (date(2023, 5, 15), 36000, "CarMax Offer"),
                (today, 35000, "KBB", "Current trade-in value"))
        # Sub-items are not just for property: a truck has insurance and a mechanic.
        db.session.add_all([
            RecurringBill(holding_id=truck.id, name="Auto insurance", payee="Example Mutual",
                          amount_cents=cents(1140), frequency="Annual",
                          next_due_date=today + timedelta(days=45)),
            HoldingVendor(holding_id=truck.id, person_id=mechanic.id, role="Mechanic",
                          notes="Has the service history."),
            BeneficiaryDesignation(holding_id=truck.id, person_id=junior.id, percentage=100,
                                   kind="will"),
        ])

        bank = holding(side="asset", type_code="bank", name="Chase Checking",
                       attributes={"institution": "Chase", "account_type": "Checking",
                                   "account_number": "XXXX-1111", "routing_number": "000000000"})
        history(bank,
                (date(2020, 1, 1), 5000, "Statement", "Account opened"),
                (date(2022, 12, 31), 12000, "Statement"),
                (today, 15000, "Online banking", "Current balance"))

        stock = holding(side="asset", type_code="investment", name="Vanguard Index Fund",
                        attributes={"institution": "Vanguard", "advisor_name": "Self-directed"})
        history(stock,
                (date(2016, 1, 1), 50000, "Statement", "Initial roll-over"),
                (date(2020, 3, 15), 65000, "Statement", "COVID dip"),
                (date(2021, 12, 31), 110000, "Statement"),
                (today, 125000, "Online portal"))
        db.session.add_all([
            BeneficiaryDesignation(holding_id=stock.id, person_id=junior.id, percentage=60,
                                   kind="trust_schedule"),
            BeneficiaryDesignation(holding_id=stock.id, person_id=sis.id, percentage=30,
                                   kind="trust_schedule", notes="Remaining 10% not yet decided"),
        ])

        iras = holding(side="asset", type_code="retirement", name="Jane's Traditional IRA",
                       entity_id=ira.id, owner_id=jane.id,
                       attributes={"institution": "Fidelity", "plan_type": "IRA",
                                   "account_number": "XXXX-7788"})
        history(iras, (date(2019, 1, 1), 90000, "Statement"), (today, 142000, "Statement"))
        db.session.add_all([
            BeneficiaryDesignation(holding_id=iras.id, person_id=john.id, percentage=100,
                                   kind="account_tod", notes="Primary beneficiary on Fidelity form"),
        ])

        pension = holding(side="asset", type_code="income_stream", name="John's Pension",
                          owner_id=john.id,
                          attributes={"payer": "Metro Teachers' Retirement", "stream_type": "Pension",
                                      "amount_per_period": cents(3200), "frequency": "Monthly"})

        rolex = holding(side="asset", type_code="jewelry", name="Rolex Submariner",
                        attributes={"location": "Safe deposit box",
                                    "appraiser_info": "Timeless Appraisals, Inc.",
                                    "appraisal_date": "2022-06-15"})
        history(rolex,
                (date(2015, 6, 15), 7500, "Purchase", "Bought new"),
                (date(2022, 6, 15), 12000, "Timeless Appraisals, Inc.", "Peak market"),
                (today, 9500, "Market correction"))

        art = holding(side="asset", type_code="art", name="Oil Painting (Landscape)",
                      attributes={"artist": "Local artist", "description": "Signed, 1998",
                                  "location": "Living room"})
        history(art,
                (date(2010, 3, 10), 1200, "Purchase", "Art fair"),
                (date(2020, 3, 10), 3500, "Insurance update"),
                (today, 4500, "Gallery estimate"))

        boat_slip = holding(side="asset", type_code="custom", name="Marina Slip B-14",
                            attributes={"type_label": "Boat slip lease",
                                        "fields": [{"name": "Marina", "value": "Harbor Point"},
                                                   {"name": "Lease ends", "value": "2031-06-30"},
                                                   {"name": "Transferable?", "value": "Yes, with marina approval"}]})
        history(boat_slip, (today, 5000, "Marina transfer fee schedule"))

        print("--- [EXAMPLE] Liabilities ---")
        mortgage = holding(side="liability", type_code="mortgage", name="Home Mortgage",
                           secured_by_id=house.id,
                           attributes={"lender": "Wells Fargo", "account_number": "LN-55501",
                                       "interest_rate": 3.5, "monthly_payment": cents(1706),
                                       "payment_due_day": 1, "original_principal": cents(380000),
                                       "maturity_date": "2040-01-01"})
        history(mortgage,
                (date(2010, 1, 1), 380000, "Loan origination", "Original principal"),
                (date(2015, 1, 1), 340000, "Statement"),
                (date(2020, 1, 1), 295000, "Refi statement"),
                (today, 250000, "Statement", "Current payoff"))

        loan = holding(side="liability", type_code="loan", name="Personal Consolidation Loan",
                       entity_id=john_personal.id, owner_id=john.id,
                       attributes={"lender": "QuickCash Corp", "interest_rate": 8.5,
                                   "monthly_payment": cents(520)})
        history(loan,
                (date(2023, 1, 15), 25000, "Origination", "Debt consolidation"),
                (date(2024, 1, 15), 15000, "Statement"),
                (today, 13000, "Online portal", "Current payoff"))

        tax = holding(side="liability", type_code="tax_owed", name="2025 Federal Balance Due",
                      attributes={"authority": "IRS", "tax_year": 2025,
                                  "due_date": date(today.year + 1, 4, 15).isoformat()})
        history(tax, (today, 2400, "CPA estimate"))

        print("--- [EXAMPLE] Equity ---")
        units = holding(side="equity", type_code="llc_units", name="Doe Rentals LLC - 50% interest",
                        ownership_pct=50.0,
                        attributes={"company": "Doe Rentals LLC", "units_held": 500,
                                    "operating_agreement_location": "Fire safe, blue folder"})
        history(units, (date(2018, 9, 1), 60000, "Capital contribution"),
                (today, 140000, "CPA valuation, half of book value"))
        db.session.add(BeneficiaryDesignation(holding_id=units.id, person_id=junior.id,
                                              percentage=100, kind="trust_schedule"))

        print("--- [EXAMPLE] The timeline ---")
        default_playbook.install(db.session)
        db.session.add_all([
            Event(kind="milestone", title="Trust signed", date=root.date_established,
                  done_at=root.date_established, phase="planning", entity_id=root.id,
                  description="Signed at Example & Partners; originals to the fire safe."),
            Event(kind="milestone", title="House retitled to the trust", date=date(2012, 6, 1),
                  done_at=date(2012, 6, 1), phase="planning", holding_id=house.id),
            Event(kind="memory", title="Junior's graduation", date=date(2019, 6, 14),
                  done_at=date(2019, 6, 14), phase="now", person_id=junior.id,
                  description="The watch was promised to him that day."),
            Event(kind="renewal", title="Renew the homeowner's policy",
                  date=today + timedelta(days=20), phase="now", holding_id=house.id,
                  assignee_id=jane.id, repeat_every=1, repeat_unit="year"),
            Event(kind="task", title="Test the smoke detectors", date=today + timedelta(days=4),
                  phase="now", holding_id=house.id, assignee_id=john.id,
                  repeat_every=6, repeat_unit="month"),
            Event(kind="task", title="Send Junior a copy of the successor trustee letter",
                  date=today - timedelta(days=3), phase="planning", assignee_id=john.id,
                  person_id=junior.id),
            Event(kind="deadline", title="Pay the 2025 federal balance", date=date(today.year + 1, 4, 15),
                  phase="now", holding_id=tax.id, assignee_id=jane.id),
            Event(kind="task", title="Decide who gets the remaining 10% of the index fund",
                  date=None, phase="planning", holding_id=stock.id, assignee_id=jane.id),
            Event(kind="task", title="Book the annual meeting with the attorney",
                  date=today - timedelta(days=10), done_at=today - timedelta(days=2),
                  phase="planning", person_id=attorney.id, assignee_id=john.id),
        ])

        db.session.commit()
        n = db.session.query(Holding).count()
        print(f"✅ seed_example.py complete: {n} holdings across assets, liabilities and equity.")


if __name__ == "__main__":
    seed_generalized_data()
