import json
import io
import zipfile
from datetime import datetime, date
from src.models import Person, Asset, Milestone, Task, Appraisal

def serialize_model(instance):
    """Converts a SQLAlchemy model instance into a dictionary."""
    data = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        if isinstance(value, (datetime, date)): # Added date support
            value = value.isoformat()
        data[column.name] = value
    return data

def generate_backup_zip():
    data = {
        "version": "1.1", # Bumped version
        "timestamp": datetime.now().isoformat(),
        "people": [serialize_model(p) for p in Person.query.all()],
        "assets": [serialize_model(a) for a in Asset.query.all()],
        "appraisals": [serialize_model(a) for a in Appraisal.query.all()], # NEW
        "milestones": [serialize_model(m) for m in Milestone.query.all()],
        "tasks": [serialize_model(t) for t in Task.query.all()]
    }

    json_dump = json.dumps(data, indent=4)

    html_content = f"""
    <html>
    <head><title>Estate Backup {data['timestamp']}</title></head>
    <body>
        <h1>Estate Data Backup</h1>
        <p>Generated: {data['timestamp']}</p>
        <hr>
        <h2>Assets & Valuations</h2>
        <ul>
            {''.join([f"<li>{a['name']} (${a.get('value_estimated', 0)})</li>" for a in data['assets']])}
        </ul>
    </body>
    </html>
    """

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"estate_data_{datetime.now().strftime('%Y%m%d')}.json", json_dump)
        zf.writestr(f"READ_ME_{datetime.now().strftime('%Y%m%d')}.html", html_content)

    memory_file.seek(0)
    return memory_file