import json
from datetime import datetime, date

from sqlalchemy import Date as SADate, DateTime as SADateTime

from src.extensions import db
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES


def _decode(column, value):
    """Turn a JSON value back into what the column expects."""
    if value is None or value == "":
        return None

    if isinstance(column.type, SADateTime):
        try:
            return datetime.fromisoformat(value)
        except (TypeError, ValueError):
            # A v1.x backup may have written a bare date here.
            return datetime.combine(date.fromisoformat(value), datetime.min.time())

    if isinstance(column.type, SADate):
        try:
            return date.fromisoformat(value)
        except (TypeError, ValueError):
            return datetime.fromisoformat(value).date()

    return value


def _row_kwargs(table, row_data):
    """Map one JSON record onto real columns.

    Unknown keys are ignored (a backup from a newer version still restores what
    this version understands) and absent keys are left out entirely, so the
    model's own default applies instead of being overwritten with None.
    """
    kwargs = {}
    for column in table.columns:
        if column.name in row_data:
            kwargs[column.name] = _decode(column, row_data[column.name])
    return kwargs


def restore_from_json(json_content):
    try:
        data = json.loads(json_content)

        if not isinstance(data, dict) or not any(key in data for key, _ in BACKUP_MODELS):
            return False, "This file does not look like an Open Estate backup."

        # 1. Clear current data - children first, so nothing is orphaned.
        for _, table in BACKUP_TABLES:
            db.session.execute(table.delete())
        for _, model in reversed(BACKUP_MODELS):
            db.session.query(model).delete()
        db.session.flush()

        # 2. Rebuild every table, parents first. Primary keys are preserved so
        #    that foreign keys and beneficiary links still point where they did.
        restored = 0
        for key, model in BACKUP_MODELS:
            for row_data in data.get(key, []):
                db.session.add(model(**_row_kwargs(model.__table__, row_data)))
                restored += 1

        # 3. Association rows last - both sides of the link now exist.
        for key, table in BACKUP_TABLES:
            rows = [_row_kwargs(table, row_data) for row_data in data.get(key, [])]
            if rows:
                db.session.execute(table.insert(), rows)
                restored += len(rows)

        db.session.commit()
        return True, f"Restore Successful ({restored} records)"

    except Exception as e:
        db.session.rollback()
        return False, str(e)
