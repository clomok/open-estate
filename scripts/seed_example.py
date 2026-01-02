import sys
import os
from datetime import date

# Add project root to path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from src.extensions import db
from src.models import Person, Asset, Milestone, Appraisal

app = create_app()

def seed_generalized_data():
    with app.app_context():
        print("--- [EXAMPLE] Wiping Database ---")
        db.drop_all()
        db.create_all()
        
        print("--- [EXAMPLE] Seeding Generic People ---")
        # Generic "John & Jane" setup
        p1 = Person(name="John Doe", role="Trustor", email="john@example.com")
        p2 = Person(name="Jane Doe", role="Trustor", email="jane@example.com")
        ben = Person(name="Junior Doe", role="Beneficiary")
        
        db.session.add_all([p1, p2, ben])
        db.session.commit()

        print("--- [EXAMPLE] Seeding One of Each Asset Type ---")
        assets = []

        # 1. Real Estate
        house = Asset(
            name="Sample Family Home",
            asset_type="RealEstate",
            is_in_trust=True,
            value_estimated=600000.0,
            owner=None, # Trust Owned
            attributes={
                "address": "123 Demo Lane, Metropolis",
                "purchase_date": "2010-01-01",
                "current_value": "600000"
            }
        )
        assets.append(house)

        # 2. Bank Account
        bank = Asset(
            name="Chase Checking",
            asset_type="Bank",
            is_in_trust=True,
            value_estimated=15000.0,
            owner=None,
            attributes={
                "institution": "Chase",
                "account_type": "Checking",
                "account_number": "XXXX-1111"
            }
        )
        assets.append(bank)

        # 3. Investment
        stock = Asset(
            name="Vanguard Index Fund",
            asset_type="Investment",
            is_in_trust=True,
            value_estimated=125000.0,
            owner=None,
            attributes={
                "institution": "Vanguard",
                "advisor_name": "Self-Directed"
            }
        )
        assets.append(stock)

        # 4. Vehicle
        car = Asset(
            name="2020 Ford F-150",
            asset_type="Vehicle",
            is_in_trust=False,
            value_estimated=35000.0,
            owner=p1,
            attributes={
                "vin": "1FTEW1E45LKD12345",
                "license_plate": "TRK-999"
            }
        )
        assets.append(car)

        # 5. Jewelry
        ring = Asset(
            name="Engagement Ring",
            asset_type="Jewelry",
            is_in_trust=False,
            value_estimated=8000.0,
            owner=p2,
            attributes={
                "location": "Master Safe",
                "appraisal_date": "2018-05-20"
            }
        )
        assets.append(ring)

        # 6. Art
        art = Asset(
            name="Oil Painting (Landscape)",
            asset_type="Art",
            is_in_trust=True,
            value_estimated=4500.0,
            owner=None,
            attributes={
                "description": "Signed by Local Artist",
                "location": "Living Room"
            }
        )
        assets.append(art)

        # 7. Liability (Loan)
        debt = Asset(
            name="Home Mortgage",
            asset_type="Liability",
            is_in_trust=True,
            value_estimated=-250000.0, # Negative
            owner=None,
            attributes={
                "lender": "Wells Fargo",
                "interest_rate": "3.5%",
                "outstanding_balance": "250000"
            }
        )
        assets.append(debt)

        # 8. Utility
        water = Asset(
            name="City Water Bill",
            asset_type="Utility",
            is_in_trust=False,
            value_estimated=0.0,
            owner=None,
            attributes={
                "provider": "City Utilities",
                "autopay_status": "Yes",
                "current_value": "45.00" # Monthly cost
            }
        )
        assets.append(water)

        db.session.add_all(assets)
        db.session.commit()

        # Add History for the Chart Demo
        print("--- [EXAMPLE] Seeding Chart History ---")
        h1 = Appraisal(asset_id=house.id, date=date(2015, 1, 1), value=450000.0, source="Purchase")
        h2 = Appraisal(asset_id=house.id, date=date(2020, 1, 1), value=550000.0, source="Refi Appraisal")
        h3 = Appraisal(asset_id=house.id, date=date.today(), value=600000.0, source="Zillow")
        db.session.add_all([h1, h2, h3])
        db.session.commit()

        print("✅ generalized 'seed_example.py' complete.")

if __name__ == "__main__":
    seed_generalized_data()