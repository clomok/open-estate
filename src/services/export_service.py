import json
import io
import zipfile
from datetime import datetime
from src.models import Person, Asset, Milestone, Task

def serialize_model(instance):
    """Converts a SQLAlchemy model instance into a dictionary."""
    data = {}
    for column in instance.__table__.columns:
        value = getattr(instance, column.name)
        # Handle DateTimes for JSON compatibility
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data

def generate_backup_zip():
    """Generates a ZIP file containing raw JSON data and a human-readable HTML summary."""
    
    # 1. Gather Data
    data = {
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
        "people": [serialize_model(p) for p in Person.query.all()],
        "assets": [serialize_model(a) for a in Asset.query.all()],
        "milestones": [serialize_model(m) for m in Milestone.query.all()],
        "tasks": [serialize_model(t) for t in Task.query.all()]
    }

    # 2. Create JSON String
    json_dump = json.dumps(data, indent=4)

    # 3. Create Simple HTML Summary (The "Apocalypse View")
    html_content = f"""
    <html>
    <head><title>Estate Backup {data['timestamp']}</title></head>
    <body>
        <h1>Estate Data Backup</h1>
        <p>Generated: {data['timestamp']}</p>
        <hr>
        <h2>People</h2>
        <ul>
            {''.join([f"<li>{p['name']} ({p.get('role', 'Unknown')})</li>" for p in data['people']])}
        </ul>
        <h2>Assets</h2>
        <ul>
            {''.join([f"<li>{a['name']} - {a.get('asset_type', 'Unknown')}</li>" for a in data['assets']])}
        </ul>
    </body>
    </html>
    """

    # 4. Zip It Up in Memory
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"estate_data_{datetime.now().strftime('%Y%m%d')}.json", json_dump)
        zf.writestr(f"READ_ME_{datetime.now().strftime('%Y%m%d')}.html", html_content)

    memory_file.seek(0)
    return memory_file