"""The schema is changed by Alembic migrations, never by wipe-and-recreate.

Three promises, each tested against a real SQLite file:
- a database at the v2 baseline, holding real v2 rows, upgrades to head with
  every row carried into the ledger;
- an empty database upgrades to head and comes out with its root trust;
- the schema the migrations build is exactly the schema the models declare,
  so `db.create_all()` (tests) and `flask db upgrade` (production) agree.
"""

import json
import os

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from src.extensions import db as _db
from src.services.backup_codec import row_kwargs
from flask import g
from tests.conftest import make_app

HERE = os.path.dirname(__file__)
MIGRATIONS = os.path.join(HERE, "..", "migrations")
BASELINE = "9bbb6e6a6bff"

# v2 backup key -> v2 table, parents first.
V2_TABLES = [
    ("people", "person"), ("trust_profile", "trust_profile"), ("milestones", "milestone"),
    ("assets", "asset"), ("appraisals", "appraisal"),
    ("asset_beneficiaries", "asset_beneficiaries"), ("tasks", "task"),
    ("structures", "property_structure"), ("location_points", "location_point"),
    ("bills", "recurring_bill"), ("vendors", "asset_vendor"),
]


@pytest.fixture
def file_app(tmp_path):
    application = make_app(tmp_path)
    with application.app_context():
        g.estate = "test"
        yield application
        _db.session.remove()
        _db.engine.dispose()


def _load_v2_rows(engine):
    with open(os.path.join(HERE, "fixtures", "backup_v2.json")) as fh:
        data = json.load(fh)
    meta = sa.MetaData()
    meta.reflect(bind=engine)
    with engine.begin() as conn:
        for key, table_name in V2_TABLES:
            table = meta.tables[table_name]
            for row in data[key]:
                conn.execute(table.insert(), [row_kwargs(table, row)])


def test_a_v2_database_upgrades_with_every_row(file_app):
    from src.models import (Entity, Holding, Person, Valuation, BeneficiaryDesignation,
                            RecurringBill, Event, Playbook)
    upgrade(directory=MIGRATIONS, revision=BASELINE)
    _load_v2_rows(_db.engine)

    upgrade(directory=MIGRATIONS, revision="head")

    s = _db.session
    assert s.query(Person).count() == 3
    assert s.query(Holding).count() == 4
    assert s.query(Valuation).count() == 2
    root = s.query(Entity).filter_by(is_root=True).one()
    assert root.name == "The Example Family Trust"
    mortgage = s.get(Holding, 12)
    assert (mortgage.side, mortgage.value_cents) == ("liability", 25000000)
    assert mortgage.attributes["interest_rate"] == 3.5
    assert s.get(Holding, 11).entity.kind == "individual"
    share = s.query(BeneficiaryDesignation).one()
    assert (share.holding_id, share.person_id, share.percentage) == (10, 2, 65.0)
    assert s.get(RecurringBill, 70).amount_cents == 820000
    task = s.get(Event, 30)
    assert (task.kind, task.holding_id) == ("task", 11)
    assert s.query(Event).filter_by(kind="milestone").count() == 1
    assert s.query(Playbook).one().trigger == "death_of_trustor"
    assert s.get(Person, 1).role_codes == ["Trustor"]
    old = set(sa.inspect(_db.engine).get_table_names())
    assert not old & {"asset", "appraisal", "trust_profile", "asset_beneficiaries",
                      "asset_vendor", "task", "milestone"}


def test_an_empty_database_upgrades_to_one_root_trust(file_app):
    from src.models import Entity
    upgrade(directory=MIGRATIONS, revision="head")
    roots = _db.session.query(Entity).filter_by(is_root=True).all()
    assert [(r.kind, r.name) for r in roots] == [("trust", "The Family Trust")]
    from src.models import Playbook
    assert [p.trigger for p in _db.session.query(Playbook)] == ["death_of_trustor"]


def test_migrations_build_exactly_the_model_schema(file_app):
    upgrade(directory=MIGRATIONS, revision="head")
    with _db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diff = compare_metadata(ctx, _db.metadata)
    assert diff == [], f"models and migrations disagree - write a migration: {diff}"
