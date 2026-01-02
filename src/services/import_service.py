import json
from datetime import datetime
from src.extensions import db
from src.models import Person, Asset, Milestone, Task

def restore_from_json(json_content):
    """
    Parses a JSON string and replaces the current database state.
    WARNING: This creates a fresh start from the backup data.
    """
    try:
        data = json.loads(json_content)
        
        # version_check = data.get('version') 
        # (Future: Add logic here to handle older versions if schema changes)

        # 1. Clear current data
        db.session.query(Task).delete()
        db.session.query(Milestone).delete()
        
        # Clear Assets (and their relationships manually if needed)
        # We delete beneficiaries association first via cascade or manual if not set
        db.session.execute(db.text("DELETE FROM asset_beneficiaries"))
        db.session.query(Asset).delete()
        db.session.query(Person).delete()
        
        # 2. Rebuild People (Preserve IDs to maintain relationships)
        id_map_people = {} # old_id -> new_instance
        
        for p_data in data.get('people', []):
            person = Person(
                id=p_data['id'], # Force ID to match backup
                name=p_data['name'],
                role=p_data.get('role'),
                email=p_data.get('email'),
                phone=p_data.get('phone'),
                attributes=p_data.get('attributes', {})
            )
            db.session.add(person)
        
        # 3. Rebuild Assets
        for a_data in data.get('assets', []):
            asset = Asset(
                id=a_data['id'],
                name=a_data['name'],
                asset_type=a_data.get('asset_type'),
                is_in_trust=a_data.get('is_in_trust'),
                owner_id=a_data.get('owner_id'),
                value_estimated=a_data.get('value_estimated'),
                attributes=a_data.get('attributes', {})
            )
            db.session.add(asset)

        # 4. Rebuild Milestones
        for m_data in data.get('milestones', []):
            # Parse date string back to object
            d_event = None
            if m_data.get('date_event'):
                d_event = datetime.fromisoformat(m_data['date_event'])

            milestone = Milestone(
                title=m_data['title'],
                description=m_data.get('description'),
                is_completed=m_data.get('is_completed'),
                date_event=d_event
            )
            db.session.add(milestone)

        db.session.commit()
        return True, "Restore Successful"

    except Exception as e:
        db.session.rollback()
        return False, str(e)