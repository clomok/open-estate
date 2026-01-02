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
    assets_owned = db.relationship('Asset', backref='owner', lazy=True)

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    asset_type = db.Column(db.String(50))
    
    is_in_trust = db.Column(db.Boolean, default=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('person.id'), nullable=True)
    
    value_estimated = db.Column(db.Float, default=0.0)
    attributes = db.Column(db.JSON, default={})
    
    beneficiaries = db.relationship('Person', secondary=asset_beneficiaries, lazy='subquery',
        backref=db.backref('future_assets', lazy=True))
    
    # NEW: History of values
    appraisals = db.relationship('Appraisal', backref='asset', lazy=True, cascade="all, delete-orphan", order_by="desc(Appraisal.date)")

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