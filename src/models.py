from datetime import datetime
from src.extensions import db

# --- Association Tables ---
asset_beneficiaries = db.Table('asset_beneficiaries',
    db.Column('asset_id', db.Integer, db.ForeignKey('asset.id'), primary_key=True),
    db.Column('person_id', db.Integer, db.ForeignKey('person.id'), primary_key=True),
    db.Column('percentage', db.Float, default=50.0)
)

class Person(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50)) 
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    attributes = db.Column(db.JSON, default={})
    
    # Relationships
    assets_owned = db.relationship('Asset', backref='owner', lazy=True)
    # New: Service links (Vendors)
    service_jobs = db.relationship('AssetVendor', backref='provider', lazy=True)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    asset_type = db.Column(db.String(50))
    
    is_in_trust = db.Column(db.Boolean, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    
    value_estimated = db.Column(db.Float, default=0.0)
    attributes = db.Column(db.JSON, default={})
    
    # Relationships
    beneficiaries = db.relationship('Person', secondary=asset_beneficiaries, lazy='subquery',
        backref=db.backref('future_assets', lazy=True))
    
    appraisals = db.relationship('Appraisal', backref='asset', lazy=True, cascade="all, delete-orphan", order_by="desc(Appraisal.date)")
    
    # --- PHASE 5 EXPANSION ---
    structures = db.relationship('PropertyStructure', backref='asset', lazy=True, cascade="all, delete-orphan")
    location_points = db.relationship('LocationPoint', backref='asset', lazy=True, cascade="all, delete-orphan")
    bills = db.relationship('RecurringBill', backref='asset', lazy=True, cascade="all, delete-orphan")
    vendors = db.relationship('AssetVendor', backref='asset', lazy=True, cascade="all, delete-orphan")

class Appraisal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    value = db.Column(db.Float, nullable=False)
    source = db.Column(db.String(100)) # e.g. "Zillow", "Official Appraiser", "KBB"
    notes = db.Column(db.Text)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='Pending') 
    due_date = db.Column(db.DateTime, nullable=True)
    is_recurring = db.Column(db.Boolean, default=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=True)

class Milestone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    date_event = db.Column(db.DateTime, nullable=True)
    description = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, default=False)

# --- PHASE 5 NEW MODELS ---

class PropertyStructure(db.Model):
    """Accommodations: Sheds, Pools, Decks, Garages."""
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)     # e.g. "North Garden Shed"
    structure_type = db.Column(db.String(50))            # e.g. "Outbuilding", "Deck", "Pool"
    description = db.Column(db.Text)
    date_built = db.Column(db.Date, nullable=True)
    date_last_maintained = db.Column(db.Date, nullable=True) # "When was this last painted/serviced?"
    notes = db.Column(db.Text)

class LocationPoint(db.Model):
    """Coordinate Ledger for specific items on a property."""
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    label = db.Column(db.String(100), nullable=False)    # e.g. "Septic Tank Lid"
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)                     # e.g. "Buried 6 inches deep, under fake rock"

class RecurringBill(db.Model):
    """Holding costs associated with an asset."""
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)     # e.g. "County Property Tax"
    payee = db.Column(db.String(100))                    # e.g. "San Diego Treasurer"
    account_number = db.Column(db.String(100))           # NEW: Migrated from Utility
    amount_estimated = db.Column(db.Float, default=0.0)
    frequency = db.Column(db.String(50))                 # e.g. "Annual", "Monthly"
    is_autopay = db.Column(db.Boolean, default=False)
    next_due_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text)

class AssetVendor(db.Model):
    """Link a Person/Contact to a specific Asset with a Role."""
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=False)
    role = db.Column(db.String(100), nullable=False)     # e.g. "Pool Cleaner", "Landscaper" (Specific to this asset)
    notes = db.Column(db.Text)