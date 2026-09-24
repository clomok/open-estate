import json
import io
import zipfile
from datetime import datetime, date

from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES

BACKUP_VERSION = "2.0"


def _encode(value):
    """Make a column value JSON-safe."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def serialize_model(instance):
    """Converts a SQLAlchemy model instance into a dictionary."""
    return {
        column.name: _encode(getattr(instance, column.name))
        for column in instance.__table__.columns
    }


def serialize_table(table, session):
    """Converts an association table (no model class) into a list of dicts."""
    return [
        {column.name: _encode(row_value) for column, row_value in zip(table.columns, row)}
        for row in session.execute(table.select()).all()
    ]


def build_backup_dict(session=None):
    """The whole database as a plain dict - every model, every association row."""
    if session is None:
        from src.extensions import db
        session = db.session

    data = {
        "version": BACKUP_VERSION,
        "timestamp": datetime.now().isoformat(),
    }
    for key, model in BACKUP_MODELS:
        data[key] = [serialize_model(row) for row in session.query(model).all()]
    for key, table in BACKUP_TABLES:
        data[key] = serialize_table(table, session)
    return data


def generate_backup_zip():
    data = build_backup_dict()
    json_dump = json.dumps(data, indent=4)

    # Human-readable companion: what is in the box, so a person opening this
    # zip in ten years can see at a glance whether anything is missing.
    contents_rows = "".join(
        f"<li>{key}: {len(data[key])}</li>"
        for key, _ in BACKUP_MODELS + BACKUP_TABLES
    )

    html_content = f"""
    <html>
    <head><title>Estate Backup {data['timestamp']}</title></head>
    <body>
        <h1>Estate Data Backup</h1>
        <p>Generated: {data['timestamp']} (format version {data['version']})</p>
        <hr>
        <h2>Assets &amp; Valuations</h2>
        <ul>
            {''.join([f"<li>{a['name']} (${a.get('value_estimated', 0)})</li>" for a in data['assets']])}
        </ul>
        <h2>Record Counts</h2>
        <ul>
            {contents_rows}
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
