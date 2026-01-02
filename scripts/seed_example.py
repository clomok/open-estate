import sys
import os
from datetime import date

# Add project root to path so imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from src.extensions import db
from src.models import Person, Asset, Appraisal

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

        print("--- [EXAMPLE] Seeding Assets with Expanded Histories ---")

        # ==========================================
        # 1. REAL ESTATE (Home)
        # ==========================================
        house = Asset(
            name="Sample Family Home",
            asset_type="RealEstate",
            is_in_trust=True,
            value_estimated=600000.0,
            owner=None,
            attributes={
                "address": "123 Demo Lane, Metropolis",
                "purchase_date": "2010-01-01",
                "purchase_price": 400000.0
            }
        )
        db.session.add(house)
        db.session.commit()

        # History: Steady appreciation with a slight dip
        db.session.add(Appraisal(asset_id=house.id, date=date(2010, 1, 1), value=400000.0, source="Purchase", notes="Original Purchase Price"))
        db.session.add(Appraisal(asset_id=house.id, date=date(2015, 6, 15), value=475000.0, source="Refi Appraisal", notes="Renovations complete"))
        db.session.add(Appraisal(asset_id=house.id, date=date(2018, 1, 1), value=525000.0, source="Tax Assessment"))
        db.session.add(Appraisal(asset_id=house.id, date=date(2020, 1, 1), value=550000.0, source="Refi Appraisal"))
        db.session.add(Appraisal(asset_id=house.id, date=date(2023, 1, 1), value=580000.0, source="Zillow"))
        db.session.add(Appraisal(asset_id=house.id, date=date.today(), value=600000.0, source="Zillow", notes="Current Estimate"))

        # ==========================================
        # 2. VEHICLE (Ford F-150)
        # ==========================================
        car = Asset(
            name="2020 Ford F-150",
            asset_type="Vehicle",
            is_in_trust=False,
            value_estimated=35000.0,
            owner=p1,
            attributes={
                "vin": "1FTEW1E45LKD12345",
                "license_plate": "TRK-999",
                "purchase_date": "2020-05-15",
                "purchase_price": 45000.0
            }
        )
        db.session.add(car)
        db.session.commit()

        # History: Depreciation curve
        db.session.add(Appraisal(asset_id=car.id, date=date(2020, 5, 15), value=45000.0, source="Purchase", notes="Dealer Invoice"))
        db.session.add(Appraisal(asset_id=car.id, date=date(2021, 5, 15), value=41000.0, source="KBB", notes="1 Year depreciation"))
        db.session.add(Appraisal(asset_id=car.id, date=date(2022, 5, 15), value=38500.0, source="KBB"))
        db.session.add(Appraisal(asset_id=car.id, date=date(2023, 5, 15), value=36000.0, source="CarMax Offer"))
        db.session.add(Appraisal(asset_id=car.id, date=date.today(), value=35000.0, source="KBB", notes="Current Trade-in Value"))

        # ==========================================
        # 3. BANK (Chase)
        # ==========================================
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
        db.session.add(bank)
        db.session.commit()
        
        # History: Fluctuation of cash
        db.session.add(Appraisal(asset_id=bank.id, date=date(2020, 1, 1), value=5000.0, source="Statement", notes="Account Opened"))
        db.session.add(Appraisal(asset_id=bank.id, date=date(2021, 6, 1), value=8500.0, source="Statement"))
        db.session.add(Appraisal(asset_id=bank.id, date=date(2022, 12, 31), value=12000.0, source="Statement", notes="Year End Bonus"))
        db.session.add(Appraisal(asset_id=bank.id, date=date(2023, 6, 30), value=10500.0, source="Statement", notes="Paid Taxes"))
        db.session.add(Appraisal(asset_id=bank.id, date=date.today(), value=15000.0, source="Online Banking", notes="Current Balance"))

        # ==========================================
        # 4. INVESTMENT (Vanguard)
        # ==========================================
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
        db.session.add(stock)
        db.session.commit()
        
        # History: Market growth with 2020 and 2022 volatility
        db.session.add(Appraisal(asset_id=stock.id, date=date(2016, 1, 1), value=50000.0, source="Statement", notes="Initial Roll-over"))
        db.session.add(Appraisal(asset_id=stock.id, date=date(2019, 1, 1), value=85000.0, source="Statement"))
        db.session.add(Appraisal(asset_id=stock.id, date=date(2020, 3, 15), value=65000.0, source="Statement", notes="COVID Dip"))
        db.session.add(Appraisal(asset_id=stock.id, date=date(2021, 12, 31), value=110000.0, source="Statement", notes="High Water Mark"))
        db.session.add(Appraisal(asset_id=stock.id, date=date(2022, 10, 1), value=95000.0, source="Statement", notes="Bear Market"))
        db.session.add(Appraisal(asset_id=stock.id, date=date.today(), value=125000.0, source="Online Portal"))

        # ==========================================
        # 5. JEWELRY (Engagement Ring)
        # ==========================================
        ring = Asset(
            name="Engagement Ring",
            asset_type="Jewelry",
            is_in_trust=False,
            value_estimated=8000.0,
            owner=p2,
            attributes={
                "location": "Master Safe",
                "appraisal_date": "2018-05-20",
                "appraiser_info": "Local Jeweler"
            }
        )
        db.session.add(ring)
        db.session.commit()

        # History: Slow appreciation / Inflation adjustment
        db.session.add(Appraisal(asset_id=ring.id, date=date(2018, 5, 20), value=8000.0, source="Local Jeweler", notes="Insurance Appraisal"))
        db.session.add(Appraisal(asset_id=ring.id, date=date(2020, 5, 20), value=8200.0, source="Insurance Adjustment"))
        db.session.add(Appraisal(asset_id=ring.id, date=date(2022, 5, 20), value=8500.0, source="Insurance Adjustment"))
        db.session.add(Appraisal(asset_id=ring.id, date=date.today(), value=8800.0, source="Est. Market Value"))

        # ==========================================
        # 6. JEWELRY (Rolex Watch)
        # ==========================================
        rolex = Asset(
            name="Rolex Submariner",
            asset_type="Jewelry",
            is_in_trust=True,
            value_estimated=9500.0,
            owner=None,
            attributes={
                "location": "Safe Deposit Box",
                "appraiser_info": "Timeless Appraisals, Inc.",
                "appraisal_date": "2022-06-15"
            }
        )
        db.session.add(rolex)
        db.session.commit()

        # History: Luxury watch boom
        db.session.add(Appraisal(asset_id=rolex.id, date=date(2015, 6, 15), value=7500.0, source="Purchase", notes="Bought New"))
        db.session.add(Appraisal(asset_id=rolex.id, date=date(2019, 6, 15), value=8200.0, source="Market Check"))
        db.session.add(Appraisal(asset_id=rolex.id, date=date(2022, 6, 15), value=12000.0, source="Timeless Appraisals, Inc.", notes="Peak Market"))
        db.session.add(Appraisal(asset_id=rolex.id, date=date(2023, 6, 15), value=10500.0, source="Chrono24"))
        db.session.add(Appraisal(asset_id=rolex.id, date=date.today(), value=9500.0, source="Market Correction", notes="Stabilized Value"))

        # ==========================================
        # 7. ART (Oil Painting)
        # ==========================================
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
        db.session.add(art)
        db.session.commit()

        # History: Artist gaining recognition
        db.session.add(Appraisal(asset_id=art.id, date=date(2010, 3, 10), value=1200.0, source="Purchase", notes="Art Fair"))
        db.session.add(Appraisal(asset_id=art.id, date=date(2015, 3, 10), value=2500.0, source="Gallery Estimate"))
        db.session.add(Appraisal(asset_id=art.id, date=date(2020, 3, 10), value=3500.0, source="Insurance Update"))
        db.session.add(Appraisal(asset_id=art.id, date=date.today(), value=4500.0, source="Initial Entry"))

        # ==========================================
        # 8. ART (Picasso)
        # ==========================================
        picasso = Asset(
            name="Picasso Sketch",
            asset_type="Art",
            is_in_trust=True,
            value_estimated=2500.0,
            owner=None,
            attributes={
                "description": "Small napkin sketch, authenticated.",
                "location": "Climate Controlled Storage",
                "appraiser_info": "Gallery 54"
            }
        )
        db.session.add(picasso)
        db.session.commit()

        # History: Long hold
        db.session.add(Appraisal(asset_id=picasso.id, date=date(2005, 11, 10), value=800.0, source="Purchase", notes="Estate Sale Find"))
        db.session.add(Appraisal(asset_id=picasso.id, date=date(2015, 11, 10), value=1500.0, source="Antiques Roadshow Est."))
        db.session.add(Appraisal(asset_id=picasso.id, date=date(2023, 11, 10), value=2500.0, source="Gallery 54", notes="Formal Authentication"))

        # ==========================================
        # 9. LIABILITY (Mortgage)
        # ==========================================
        mortgage = Asset(
            name="Home Mortgage",
            asset_type="Liability",
            is_in_trust=True,
            value_estimated=-250000.0,
            owner=None,
            attributes={
                "lender": "Wells Fargo",
                "interest_rate": "3.5%",
                "outstanding_balance": "250000"
            }
        )
        db.session.add(mortgage)
        db.session.commit()

        # History: Paying down principal (Value gets closer to 0, so "increases")
        db.session.add(Appraisal(asset_id=mortgage.id, date=date(2010, 1, 1), value=-380000.0, source="Loan Origination", notes="Original Principal"))
        db.session.add(Appraisal(asset_id=mortgage.id, date=date(2015, 1, 1), value=-340000.0, source="Statement"))
        db.session.add(Appraisal(asset_id=mortgage.id, date=date(2020, 1, 1), value=-295000.0, source="Refi Statement"))
        db.session.add(Appraisal(asset_id=mortgage.id, date=date(2023, 1, 1), value=-270000.0, source="Statement"))
        db.session.add(Appraisal(asset_id=mortgage.id, date=date.today(), value=-250000.0, source="Statement", notes="Current Payoff"))

        # ==========================================
        # 10. LIABILITY (Personal Loan)
        # ==========================================
        loan = Asset(
            name="Personal Consolidation Loan",
            asset_type="Liability",
            is_in_trust=False,
            value_estimated=-13000.0,
            owner=p1,
            attributes={
                "lender": "QuickCash Corp",
                "interest_rate": "8.5%",
                "outstanding_balance": "13000"
            }
        )
        db.session.add(loan)
        db.session.commit()

        # History: Rapid Paydown
        db.session.add(Appraisal(asset_id=loan.id, date=date(2023, 1, 15), value=-25000.0, source="Origination", notes="Debt Consolidation"))
        db.session.add(Appraisal(asset_id=loan.id, date=date(2023, 6, 15), value=-20000.0, source="Statement"))
        db.session.add(Appraisal(asset_id=loan.id, date=date(2024, 1, 15), value=-15000.0, source="Statement"))
        db.session.add(Appraisal(asset_id=loan.id, date=date.today(), value=-13000.0, source="Online Portal", notes="Current Payoff"))

        # ==========================================
        # 11. UTILITY (Water Bill)
        # ==========================================
        water = Asset(
            name="City Water Bill",
            asset_type="Utility",
            is_in_trust=False,
            value_estimated=0.0,
            owner=None,
            attributes={
                "provider": "City Utilities",
                "autopay_status": "Yes",
                "current_value": "45.00"
            }
        )
        db.session.add(water)
        db.session.commit()
        
        # Utilities usually don't have equity value history, but we'll add a placeholder
        db.session.add(Appraisal(asset_id=water.id, date=date.today(), value=0.0, source="System", notes="Recurring Liability Placeholder"))

        db.session.commit()
        print("✅ generalized 'seed_example.py' complete with RICH histories.")

if __name__ == "__main__":
    seed_generalized_data()