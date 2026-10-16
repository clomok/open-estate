"""Bring every estate's database up to the current schema. Runs at container
start, before gunicorn, so new code never meets an old schema; and with
`--estate <slug>` on one estate, which is how a new estate gets built.

Before it changes a database it copies the file to that estate's backups/
folder, named for the revision it was at - the way back if a migration ever
goes wrong, since the v3 migration cannot be downgraded.

A fresh install (no estates.json) starts with one empty `demo` estate. An
install still in the one-folder-per-dataset layout is refused with the
command that adopts it, rather than started empty beside the real data.

It refuses, rather than guesses, when the database has tables but no
migration history it recognises.
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlalchemy as sa  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from flask_migrate import upgrade, stamp  # noqa: E402

from flask import g  # noqa: E402

from app import create_app  # noqa: E402
from src import estates  # noqa: E402
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


def upgrade_estate(app, slug):
    with app.app_context():
        g.estate = slug
        os.makedirs(estates.estate_dir(app.config["ESTATES_ROOT"], slug), exist_ok=True)
        engine = db.engine
        head = ScriptDirectory(os.path.join(MIGRATIONS)).get_current_head()
        tables = set(sa.inspect(engine).get_table_names()) - {"alembic_version"}
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()

        if current == head:
            print(f"[upgrade_db] {slug}: schema is current ({head}).")
            return 0

        if current is None and tables:
            if tables == BASELINE_TABLES:
                print(f"[upgrade_db] {slug}: unversioned database with the v2 baseline tables: "
                      f"stamping {BASELINE} before upgrading.")
            else:
                print(f"[upgrade_db] {slug}: REFUSED: this database has tables but no migration "
                      "history, and they are not the v2 baseline. Restore it from a "
                      "backup into an empty estate instead.", file=sys.stderr)
                return 1

        path = engine.url.database
        if path and os.path.exists(path) and tables:
            print(f"[upgrade_db] {slug}: copied the database to "
                  f"{_snapshot(path, current or 'unversioned')}")

        if current is None and tables:
            stamp(directory=MIGRATIONS, revision=BASELINE)
        upgrade(directory=MIGRATIONS)
        print(f"[upgrade_db] {slug}: upgraded {current or 'empty'} -> {head}.")
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--estate", help="upgrade only this estate (it need not be registered yet)")
    args = ap.parse_args(argv)

    app = create_app()
    root = app.config["ESTATES_ROOT"]

    if args.estate:
        return upgrade_estate(app, estates.check_slug(args.estate))

    registered = estates.load(root)
    if not registered:
        legacy = [p for p in ("estate.db",) if os.path.exists(os.path.join(root, p))]
        legacy += sorted(d for d in os.listdir(root) if d != "estates"
                         and os.path.exists(os.path.join(root, d, "estate.db"))) \
            if os.path.isdir(root) else []
        if legacy:
            print("[upgrade_db] REFUSED: this install still uses the old one-container-per-"
                  f"dataset layout ({', '.join(legacy)}). Stop the stack and run, on the host: "
                  "python3 scripts/estate_admin.py adopt <name>  - see datasets/README.md.",
                  file=sys.stderr)
            return 1
        estates.add(root, "demo", "Demo data")
        print("[upgrade_db] fresh install: registered an empty 'demo' estate.")
        registered = estates.load(root)

    worst = 0
    for entry in registered:
        worst = max(worst, upgrade_estate(app, entry["slug"]))
    return worst


if __name__ == "__main__":
    sys.exit(main())
