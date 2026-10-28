import json
import io
import zipfile
from datetime import datetime
from html import escape

from src.money import format_cents
from src.services.backup_codec import encode
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES, BACKUP_VERSION


def serialize_model(instance):
    """Converts a SQLAlchemy model instance into a dictionary."""
    return {
        column.name: encode(getattr(instance, column.name))
        for column in instance.__table__.columns
    }


def serialize_table(table, session):
    """Converts an association table (no model class) into a list of dicts."""
    return [
        {column.name: encode(row_value) for column, row_value in zip(table.columns, row)}
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
        data[key] = [serialize_model(row)
                     for row in session.query(model).order_by(model.id).all()]
    for key, table in BACKUP_TABLES:
        data[key] = serialize_table(table, session)
    return data


def _readme(data):
    """Human-readable companion: what is in the box, so a person opening this
    zip in ten years can see at a glance whether anything is missing."""
    contents_rows = "".join(
        f"<li>{escape(key)}: {len(data[key])}</li>"
        for key, _ in BACKUP_MODELS + BACKUP_TABLES
    )
    sections = []
    for side, title in (("asset", "Assets"), ("liability", "Liabilities"), ("equity", "Equity")):
        items = [h for h in data["holdings"] if h["side"] == side]
        if items:
            rows = "".join(
                f"<li>{escape(h['name'])} ({format_cents(h['value_cents'])})</li>" for h in items)
            sections.append(f"<h2>{title}</h2><ul>{rows}</ul>")
    root = next((e for e in data["entities"] if e["is_root"]), None)
    heading = escape(root["name"]) if root else "Estate"
    return f"""
    <html>
    <head><meta charset="utf-8"><title>{heading} - backup {data['timestamp']}</title></head>
    <body>
        <h1>{heading} - data backup</h1>
        <p>Generated: {data['timestamp']} (format version {data['version']})</p>
        <p>The printed binder is saved beside this file as BINDER_&lt;date&gt;.html:
        open it in a browser and print it, with sensitive details masked.</p>
        <hr>
        {''.join(sections)}
        <h2>Record counts</h2>
        <ul>{contents_rows}</ul>
    </body>
    </html>
    """


def _binder_html():
    """The printed binder (toggles off, sensitive details masked) as one
    self-contained file, so the paper can be rebuilt from the zip alone."""
    from flask import current_app
    from src.routes.binder import BASE_OPTIONS, render_binder
    with current_app.test_request_context():
        return render_binder(dict(BASE_OPTIONS), offline=True)


def generate_backup_zip():
    data = build_backup_dict()
    json_dump = json.dumps(data, indent=4)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"estate_data_{datetime.now().strftime('%Y%m%d')}.json", json_dump)
        zf.writestr(f"READ_ME_{datetime.now().strftime('%Y%m%d')}.html", _readme(data))
        zf.writestr(f"BINDER_{datetime.now().strftime('%Y%m%d')}.html", _binder_html())

    memory_file.seek(0)
    return memory_file
