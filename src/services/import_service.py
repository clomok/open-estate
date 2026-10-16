import json

from src.extensions import db
from src.services.backup_codec import parent_first, row_kwargs
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES, SELF_REFERENCES
from src.services import v2_upgrade, v3_upgrade

# Keys only an asset-era (v1/v2) backup has. Seeing any of them means the
# file goes through the v2 -> v3 converter before it is restored.
_LEGACY_KEYS = {"assets", "appraisals", "trust_profile", "asset_beneficiaries"}
# Keys a v3 backup has that v4 replaced with `events`.
_V3_KEYS = {"tasks", "milestones"}


def _major_version(data):
    try:
        return int(str(data.get("version", "")).split(".")[0])
    except ValueError:
        return None


def upgrade_payload(data):
    """Any supported backup dict -> the current (v4) layout, one step at a
    time: v1/v2 -> v3 -> v4. Each step is frozen once released."""
    major = _major_version(data)
    if major is None:
        if _LEGACY_KEYS & set(data):
            major = 2
        elif _V3_KEYS & set(data):
            major = 3
        else:
            return data
    if major < 3:
        data, major = v2_upgrade.convert(data), 3
    if major == 3:
        data = v3_upgrade.convert(data)
    return data


def restore_from_json(json_content):
    try:
        data = json.loads(json_content)

        if not isinstance(data, dict) or not (
                any(key in data for key, _ in BACKUP_MODELS) or _LEGACY_KEYS & set(data)):
            return False, "This file does not look like an Open Estate backup."

        upgraded = upgrade_payload(data)
        upgraded_from = data.get("version", "an older version") if upgraded is not data else None
        data = upgraded

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
            rows = data.get(key, [])
            if key in SELF_REFERENCES:
                rows = parent_first(rows, SELF_REFERENCES[key])
            for row_data in rows:
                db.session.add(model(**row_kwargs(model.__table__, row_data)))
                restored += 1
                # A self-referencing table is flushed row by row so the row it
                # points at is in the database before it is referenced.
                if key in SELF_REFERENCES:
                    db.session.flush()
            # Flush per table: the unit of work only orders inserts along
            # mapped relationships, and with foreign keys enforced the
            # parent-first order above must be the order that reaches SQLite.
            db.session.flush()

        # 3. Association rows last - both sides of the link now exist.
        for key, table in BACKUP_TABLES:
            rows = [row_kwargs(table, row_data) for row_data in data.get(key, [])]
            if rows:
                db.session.execute(table.insert(), rows)
                restored += len(rows)

        from src.services.estate import check_single_root
        check_single_root()

        # The forms refuse a bad holding detail; a backup must not sneak one
        # in. A hand-edited file with "$1,200" in a money field would restore
        # cleanly and then break every page that shows that holding.
        from src.models import Holding
        from src.holding_types import validate_attributes
        for h in Holding.query.all():
            if h.htype is not None:
                problems = validate_attributes(h.htype, h.attributes)
                if problems:
                    raise ValueError(f"holding {h.id} ({h.name}): " + "; ".join(problems))

        db.session.commit()
        msg = f"Restore Successful ({restored} records)"
        if upgraded_from:
            msg += f" - upgraded from backup format {upgraded_from}"
        return True, msg

    except Exception as e:
        db.session.rollback()
        return False, str(e)
