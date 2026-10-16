"""Backup and restore must carry the whole database, not part of it.

The bug these tests exist to prevent: the UI collects data that the backup
silently drops, so the "durability layer" hands back a lighter estate than it
was given. Before v2, Phase 5/6 models, every Task, and every beneficiary
percentage were lost on a backup-restore cycle.
"""

import json
import os
import zipfile
from datetime import date

from src.models import (
    BeneficiaryDesignation,
    Entity,
    Event,
    Holding,
    HoldingVendor,
    LocationPoint,
    Person,
    PersonRole,
    Playbook,
    PlaybookStep,
    PropertyStructure,
    RecurringBill,
    Valuation,
)
from src.services.backup_schema import BACKUP_MODELS, BACKUP_TABLES, BACKUP_VERSION
from src.services.export_service import build_backup_dict, generate_backup_zip
from src.services.import_service import restore_from_json
from tests.fixtures_estate import _populate, _wipe

V2_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "backup_v2.json")


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


def test_backup_is_version_4(db):
    _populate(db)
    assert build_backup_dict()["version"] == BACKUP_VERSION == "4.0"


def test_round_trip_preserves_every_table(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)

    assert db.session.query(Holding).count() == 0

    ok, msg = restore_from_json(payload)
    assert ok, msg

    assert db.session.query(Person).count() == 3
    assert db.session.query(PersonRole).count() == 4
    assert db.session.query(Entity).count() == 2
    assert db.session.query(Holding).count() == 5
    assert db.session.query(Valuation).count() == 1
    assert db.session.query(BeneficiaryDesignation).count() == 2
    assert db.session.query(Event).count() == 4
    assert db.session.query(Playbook).count() == 1
    assert db.session.query(PlaybookStep).count() == 2
    assert db.session.query(PropertyStructure).count() == 1
    assert db.session.query(LocationPoint).count() == 1
    assert db.session.query(RecurringBill).count() == 2
    assert db.session.query(HoldingVendor).count() == 1


def test_round_trip_preserves_beneficiary_shares(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)
    assert restore_from_json(payload)[0]

    house = db.session.get(Holding, 10)
    shares = {(d.person_id, d.percentage, d.kind) for d in house.beneficiary_designations}
    assert shares == {(2, 65.0, "trust_schedule"), (1, 35.0, "trust_schedule")}
    assert house.share_totals() == {"trust_schedule": 100}


def test_round_trip_preserves_field_values(db):
    _populate(db)
    payload = json.dumps(build_backup_dict())
    _wipe(db)
    assert restore_from_json(payload)[0]

    bill = db.session.get(RecurringBill, 70)
    assert bill.account_number == "ACCT-9911"
    assert bill.next_due_date == date(2026, 11, 1)      # Date survives as a Date
    assert bill.is_autopay is False
    assert bill.amount_cents == 820050                  # cents, exactly

    point = db.session.get(LocationPoint, 60)
    assert (point.latitude, point.longitude) == (33.5427, -117.6631)

    task = db.session.get(Event, 30)
    assert (task.date, task.holding_id, task.assignee_id) == (date(2026, 3, 15), 11, 1)
    review = db.session.get(Event, 31)
    assert (review.done_at, review.repeat_every, review.repeat_unit) == (date(2026, 1, 6), 1, "year")
    assert db.session.get(Event, 33).source == "bill:70@2025-11-01"
    step = db.session.get(PlaybookStep, 1)
    assert (step.who_role, step.document_type) == ("SuccessorTrustee", "POLST")

    root = db.session.get(Entity, 1)
    assert root.is_root and root.kind == "trust"
    assert root.name == "The Example Family Trust"
    assert root.date_established == date(2014, 2, 9)
    assert root.date_death_actual is None
    assert db.session.get(Entity, 2).parent_id == 1

    house = db.session.get(Holding, 10)
    assert house.attributes == {"address": "1 Example Way", "purchase_price": 40000050}
    assert house.in_trust is True
    assert db.session.get(Holding, 11).entity_id == 2   # not coerced to the trust

    mortgage = db.session.get(Holding, 12)
    assert (mortgage.side, mortgage.value_cents, mortgage.secured_by_id) == ("liability", 25000000, 10)
    stake = db.session.get(Holding, 13)
    assert (stake.side, stake.ownership_pct) == ("equity", 50.0)
    assert db.session.get(Holding, 14).type_label == "Boat slip lease"

    tony = db.session.get(Person, 1)
    assert tony.role_codes == ["Trustor", "Trustee"]
    assert tony.last_verified == date(2026, 1, 2)
    assert db.session.get(Person, 3).kind == "organisation"
    assert db.session.get(Holding, 11).last_verified == date(2025, 12, 1)
    assert tony.created_at is not None and tony.updated_at is not None

    structure = db.session.get(PropertyStructure, 50)
    assert structure.date_last_maintained == date(2025, 8, 14)


def test_liability_restores_even_when_listed_before_its_asset(db):
    """Restore orders self-references itself; a file is not trusted to."""
    _populate(db)
    data = build_backup_dict()
    data["holdings"].sort(key=lambda h: h["side"] != "liability")
    _wipe(db)
    ok, msg = restore_from_json(json.dumps(data))
    assert ok, msg
    assert db.session.get(Holding, 12).secured_by_id == 10


def test_round_trip_through_the_real_zip(db):
    """The path a user actually takes: download the zip, upload it back."""
    _populate(db)
    buffer = generate_backup_zip()

    with zipfile.ZipFile(buffer) as archive:
        name = next(n for n in archive.namelist() if n.endswith(".json"))
        payload = archive.read(name)
        readme = archive.read(next(n for n in archive.namelist() if n.endswith(".html"))).decode()
    assert "Home Mortgage ($250,000)" in readme

    _wipe(db)
    ok, msg = restore_from_json(payload)
    assert ok, msg
    assert db.session.query(Event).count() == 4
    assert db.session.get(Entity, 1).notes == "Reviewed by counsel"


def test_restore_is_idempotent(db):
    """Restoring twice leaves one estate, not two."""
    _populate(db)
    payload = json.dumps(build_backup_dict())
    assert restore_from_json(payload)[0]
    assert restore_from_json(payload)[0]
    assert db.session.query(Holding).count() == 5
    assert db.session.query(BeneficiaryDesignation).count() == 2
    assert db.session.query(Entity).filter_by(is_root=True).count() == 1


def test_restore_rejects_a_foreign_file(db):
    _populate(db)
    ok, msg = restore_from_json(json.dumps({"hello": "world"}))
    assert not ok
    assert "Open Estate backup" in msg
    assert db.session.query(Holding).count() == 5, "a rejected file must not wipe the estate"


def test_a_failed_restore_leaves_the_estate_intact(db):
    """Half a restore is worse than none: the wipe and the rebuild are one
    transaction, so a corrupt record rolls the whole thing back."""
    _populate(db)
    broken = build_backup_dict()
    broken["bills"][0]["next_due_date"] = "not-a-date"

    ok, _ = restore_from_json(json.dumps(broken))
    assert not ok
    assert db.session.query(Holding).count() == 5
    assert db.session.query(RecurringBill).count() == 2
    assert db.session.get(RecurringBill, 70).next_due_date == date(2026, 11, 1)


def test_a_restore_without_a_root_trust_is_refused(db):
    _populate(db)
    data = build_backup_dict()
    data["entities"] = []
    for row in data["holdings"] + data["events"]:
        row["entity_id"] = None
    ok, msg = restore_from_json(json.dumps(data))
    assert not ok and "root trust" in msg
    assert db.session.query(Entity).count() == 2


# --- v2 files ----------------------------------------------------------------

def _v2_payload():
    with open(V2_FIXTURE) as fh:
        return fh.read()


def test_a_v2_backup_restores_into_the_v3_ledger(db):
    """tests/fixtures/backup_v2.json was written by the real v2 exporter."""
    ok, msg = restore_from_json(_v2_payload())
    assert ok, msg
    assert "upgraded from backup format 2.0" in msg

    root = db.session.query(Entity).filter_by(is_root=True).one()
    assert root.name == "The Example Family Trust"
    assert root.next_review_date == date(2027, 2, 9)

    house = db.session.get(Holding, 10)
    assert (house.side, house.type_code, house.value_cents) == ("asset", "real_estate", 75000000)
    assert house.in_trust

    # v2 kept debts as negative assets, with their numbers as strings.
    mortgage = db.session.get(Holding, 12)
    assert (mortgage.side, mortgage.type_code, mortgage.value_cents) == ("liability", "loan", 25000000)
    assert mortgage.attributes == {"lender": "Example Bank", "account_number": "LN-4417",
                                   "interest_rate": 3.5, "payment_due_day": 1}
    assert mortgage.notes == "Refinanced 2020"
    assert [v.value_cents for v in mortgage.valuations] == [38000000]

    # Not in the trust in v2 -> an add-on entity of kind `individual`.
    car = db.session.get(Holding, 11)
    assert car.entity.kind == "individual" and car.entity.person_id == 1
    ring = db.session.get(Holding, 13)
    assert ring.entity.name == "Held outside the trust"
    assert ring.value_cents == 800050
    assert ring.notes == "Insurance rider: R-22"         # unknown key kept, not dropped
    assert ring.attributes["appraisal_date"] == "2018-05-20"

    share = db.session.query(BeneficiaryDesignation).one()
    assert (share.holding_id, share.person_id, share.percentage, share.kind) == \
        (10, 2, 65.0, "trust_schedule")
    assert db.session.get(Person, 1).role_codes == ["Trustor"]
    assert db.session.get(RecurringBill, 70).amount_cents == 820000
    task = db.session.get(Event, 30)
    assert (task.kind, task.date, task.done_at) == ("task", date(2026, 3, 15), None)


def test_older_backup_still_restores(db):
    """A v1.1 file predates the Phase 5/6 sections; it must still load."""
    full = json.loads(_v2_payload())
    legacy = {key: full[key] for key in
              ("timestamp", "people", "assets", "appraisals", "milestones", "tasks")}
    legacy["version"] = "1.1"
    ok, msg = restore_from_json(json.dumps(legacy))
    assert ok, msg
    assert db.session.query(Person).count() == 3
    assert db.session.query(RecurringBill).count() == 0
    # No trust_profile section: v3 still gets its root trust.
    assert db.session.query(Entity).filter_by(is_root=True).count() == 1


def test_every_converted_holding_passes_the_registry(db):
    from src.holding_types import validate_attributes
    assert restore_from_json(_v2_payload())[0]
    for h in db.session.query(Holding):
        assert validate_attributes(h.htype, h.attributes) == [], h.name


# --- v3 files ----------------------------------------------------------------

def _v3_payload():
    from src.services import v2_upgrade
    data = v2_upgrade.convert(json.loads(_v2_payload()))
    data["version"] = "3.0"
    return data


def test_a_v3_backup_restores_with_tasks_and_milestones_as_events(db):
    v3 = _v3_payload()
    v3["tasks"][1]["updated_at"] = "2026-01-07T10:00:00"     # Done, recurring
    ok, msg = restore_from_json(json.dumps(v3))
    assert ok, msg
    assert "upgraded from backup format 3.0" in msg

    by_kind = {}
    for e in db.session.query(Event).order_by(Event.id):
        by_kind.setdefault(e.kind, []).append(e)
    tasks, milestones = by_kind["task"], by_kind["milestone"]
    assert [t.id for t in tasks] == [30, 31]
    assert tasks[0].date == date(2026, 3, 15) and tasks[0].done_at is None
    assert tasks[1].done_at == date(2026, 1, 7)
    assert tasks[1].description == "(was marked recurring)" and not tasks[1].repeats
    # Milestones are numbered after the last task, so nothing collides.
    assert [m.id for m in milestones] == [32]
    assert milestones[0].title == v3["milestones"][0]["title"]

    # An old file carries no playbook; it comes back with the default one.
    pb = db.session.query(Playbook).one()
    assert pb.trigger == "death_of_trustor"
    from src.services.default_playbook import STEPS
    assert len(pb.steps) == len(STEPS)


def test_a_v3_backup_with_no_version_is_still_recognised(db):
    v3 = _v3_payload()
    v3.pop("version", None)
    ok, msg = restore_from_json(json.dumps(v3))
    assert ok, msg
    assert db.session.query(Event).filter_by(kind="task").count() == 2
