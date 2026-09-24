"""Backup and restore must carry the whole database, not part of it.

The bug these tests exist to prevent: the UI collects data that the backup
silently drops, so the "durability layer" hands back a lighter estate than it
was given. Before this file, Phase 5/6 models, every Task, and every
beneficiary percentage were lost on a backup-restore cycle.
"""

import json
import zipfile
from datetime import date, datetime

from src.models import (
    asset_beneficiaries,
    Appraisal,
    Asset,
    AssetVendor,
    LocationPoint,
    Milestone,
    Person,
    PropertyStructure,
    RecurringBill,
    Task,
    TrustProfile,
)
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES
from src.services.export_service import build_backup_dict, generate_backup_zip
from src.services.import_service import restore_from_json
from tests.fixtures_estate import _populate, _wipe


def test_every_table_is_covered_by_the_backup(db):
    """The guard. A new model that nobody adds to backup_schema fails here,
    instead of failing silently in a restore years from now."""
    known = {model.__table__.name for _, model in BACKUP_MODELS}
    known |= {table.name for _, table in BACKUP_TABLES}
    all_tables = set(db.metadata.tables) - {"alembic_version"}
    assert all_tables - known == set(), (
        "These tables are in the schema but not in src/services/backup_schema.py, "
        "so their data would be lost on backup/restore."
    )


def test_round_trip_preserves_every_table(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)

    assert db.session.query(Asset).count() == 0

    ok, msg = restore_from_json(payload)
    assert ok, msg

    assert db.session.query(Person).count() == 3
    assert db.session.query(Asset).count() == 2
    assert db.session.query(Appraisal).count() == 1
    assert db.session.query(Task).count() == 2          # was dropped entirely before
    assert db.session.query(Milestone).count() == 1
    assert db.session.query(PropertyStructure).count() == 1
    assert db.session.query(LocationPoint).count() == 1
    assert db.session.query(RecurringBill).count() == 1
    assert db.session.query(AssetVendor).count() == 1
    assert db.session.query(TrustProfile).count() == 1


def test_round_trip_preserves_beneficiary_shares(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)
    assert restore_from_json(payload)[0]

    link = db.session.execute(asset_beneficiaries.select()).all()
    assert len(link) == 1
    assert (link[0].asset_id, link[0].person_id, link[0].percentage) == (10, 2, 65.0)


def test_round_trip_preserves_field_values(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)
    assert restore_from_json(payload)[0]

    bill = db.session.get(RecurringBill, 70)
    assert bill.account_number == "ACCT-9911"
    assert bill.next_due_date == date(2026, 11, 1)      # Date survives as a Date
    assert bill.is_autopay is False
    assert bill.amount_estimated == 8200.0

    point = db.session.get(LocationPoint, 60)
    assert (point.latitude, point.longitude) == (33.5427, -117.6631)

    task = db.session.get(Task, 30)
    assert task.due_date == datetime(2026, 3, 15, 9, 0)  # DateTime survives as one
    assert task.asset_id == 11

    profile = db.session.get(TrustProfile, 1)
    assert profile.name == "The Example Family Trust"
    assert profile.date_established == date(2014, 2, 9)
    assert profile.date_death_actual is None

    house = db.session.get(Asset, 10)
    assert house.attributes == {"address": "1 Example Way"}
    assert house.is_in_trust is True
    assert db.session.get(Asset, 11).is_in_trust is False  # not coerced to a default

    structure = db.session.get(PropertyStructure, 50)
    assert structure.date_last_maintained == date(2025, 8, 14)


def test_round_trip_through_the_real_zip(db):
    """The path a user actually takes: download the zip, upload it back."""
    _populate(db)
    buffer = generate_backup_zip()

    with zipfile.ZipFile(buffer) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".json"))
        payload = archive.read(name)

    _wipe(db)
    ok, msg = restore_from_json(payload)
    assert ok, msg
    assert db.session.query(Task).count() == 2
    assert db.session.get(TrustProfile, 1).notes == "Reviewed by counsel"


def test_restore_is_idempotent(db):
    """Restoring twice leaves one estate, not two."""
    _populate(db)
    payload = json.dumps(build_backup_dict())
    assert restore_from_json(payload)[0]
    assert restore_from_json(payload)[0]
    assert db.session.query(Asset).count() == 2
    assert len(db.session.execute(asset_beneficiaries.select()).all()) == 1


def test_older_backup_still_restores(db):
    """A v1.1 file predates the Phase 5/6 sections; it must still load."""
    _populate(db)
    full = build_backup_dict()
    legacy = {
        "version": "1.1",
        "timestamp": full["timestamp"],
        "people": full["people"],
        "assets": full["assets"],
        "appraisals": full["appraisals"],
        "milestones": full["milestones"],
        "tasks": full["tasks"],
    }
    _wipe(db)
    ok, msg = restore_from_json(json.dumps(legacy))
    assert ok, msg
    assert db.session.query(Person).count() == 3
    assert db.session.query(RecurringBill).count() == 0


def test_restore_rejects_a_foreign_file(db):
    _populate(db)
    ok, msg = restore_from_json(json.dumps({"hello": "world"}))
    assert not ok
    assert "Open Estate backup" in msg
    assert db.session.query(Asset).count() == 2, "a rejected file must not wipe the estate"


def test_a_failed_restore_leaves_the_estate_intact(db):
    """Half a restore is worse than none: the wipe and the rebuild are one
    transaction, so a corrupt record rolls the whole thing back."""
    _populate(db)
    broken = build_backup_dict()
    broken["bills"][0]["next_due_date"] = "not-a-date"

    ok, _ = restore_from_json(json.dumps(broken))
    assert not ok
    assert db.session.query(Asset).count() == 2
    assert db.session.query(RecurringBill).count() == 1
    assert db.session.get(RecurringBill, 70).next_due_date == date(2026, 11, 1)
