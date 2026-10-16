"""Bring this dataset's database up to the current schema. Runs at container
start, before gunicorn, so new code never meets an old schema.

Before it changes anything it copies the database file to
instance/backups/, named for the revision it was at - the way back if a
migration ever goes wrong, since the v3 migration cannot be downgraded.

It refuses, rather than guesses, when the database has tables but no
migration history it recognises.
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from flask_migrate import upgrade, stamp  # noqa: E402

from app import create_app  # noqa: E402
from src.extensions import db  # noqa: E402

MIGRATIONS = os.path.join(os.path.dirname(__file__), "..", "migrations")
BASELINE = "9bbb6e6a6bff"
# The tables the baseline migration creates. A database built by the old
# create_all() path has exactly these and no alembic_version row.
BASELINE_TABLES = {"milestone", "person", "trust_profile", "asset", "appraisal",
                   "asset_beneficiaries", "asset_vendor", "location_point",
                   "property_structure", "recurring_bill", "task"}


def _snapshot(path, label):
    folder = os.path.join(os.path.dirname(path), "backups")
    os.makedirs(folder, exist_ok=True)
    stamp_ = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = os.path.join(folder, f"estate-{stamp_}-before-{label}.db")
    # SQLite's own backup API: a consistent copy even if something has it open.
    src, dst = sqlite3.connect(path), sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return target


def main():
    app = create_app()
    with app.app_context():
        engine = db.engine
        head = ScriptDirectory(os.path.join(MIGRATIONS)).get_current_head()
        tables = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()

        if current == head:
            print(f"[upgrade_db] schema is current ({head}).")
            return 0

        if current is None and tables:
            if tables == BASELINE_TABLES:
                print("[upgrade_db] unversioned database with the v2 baseline tables: "
                      f"stamping {BASELINE} before upgrading.")
            else:
                print("[upgrade_db] REFUSED: this database has tables but no migration "
                      "history, and they are not the v2 baseline. Restore it from a "
                      "backup into an empty dataset instead.", file=sys.stderr)
                return 1

        path = engine.url.database
        if engine.url.get_backend_name() == "sqlite" and path and os.path.exists(path) and tables:
            print(f"[upgrade_db] copied the database to {_snapshot(path, current or 'unversioned')}")

        if current is None and tables:
            stamp(directory=MIGRATIONS, revision=BASELINE)
        upgrade(directory=MIGRATIONS)
        print(f"[upgrade_db] upgraded {current or 'empty'} -> {head}.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
