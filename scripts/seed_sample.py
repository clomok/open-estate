# THIS FILE IS SAFE TO COMMIT
# It populates the DB with "John Doe" dummy data for testing.
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from src.extensions import db
from src.models import Person, Asset, Milestone

app = create_app()

def seed_data():
    with app.app_context():
        db.drop_all()
        db.create_all()
        
        print("Seeding Dummy Data...")
        trustor = Person(name="Trustor (Example)", role="Trustor", attributes={"notes": "The Grantor"})
        ben1 = Person(name="Beneficiary A", role="Beneficiary")
        
        house = Asset(name="Example House", asset_type="Property", is_in_trust=True, value_estimated=500000.0)
        
        db.session.add_all([trustor, ben1, house])
        db.session.commit()
        print("Dummy Data Seeded!")

if __name__ == "__main__":
    seed_data()