"""scripts/upgrade_db.py - the step the container runs before gunicorn."""

import os
import subprocess
import sys

import sqlalchemy as sa
from flask_migrate import upgrade

from tests.test_migrations import MIGRATIONS, BASELINE, _load_v2_rows, file_app  # noqa: F401
from src.extensions import db as _db

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run(db_path):
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{db_path}",
               ADMIN_PASSWORD="test_password", SECRET_KEY="test_secret_key")
    return subprocess.run([sys.executable, "scripts/upgrade_db.py"], cwd=ROOT, env=env,
                          capture_output=True, text=True)


def _db_path(app):
    return _db.engine.url.database


def test_upgrades_a_v2_database_and_keeps_a_copy(file_app):
    upgrade(directory=MIGRATIONS, revision=BASELINE)
    _load_v2_rows(_db.engine)
    path = _db_path(file_app)
    _db.engine.dispose()

    result = _run(path)
    assert result.returncode == 0, result.stderr
    assert "upgraded 9bbb6e6a6bff ->" in result.stdout

    backups = os.listdir(os.path.join(os.path.dirname(path), "backups"))
    assert len(backups) == 1 and backups[0].endswith(f"before-{BASELINE}.db")
    copy = sa.create_engine(f"sqlite:///{os.path.join(os.path.dirname(path), 'backups', backups[0])}")
    with copy.connect() as conn:       # the copy is the untouched v2 database
        assert conn.execute(sa.text("SELECT count(*) FROM asset")).scalar() == 4

    again = _run(path)
    assert again.returncode == 0 and "schema is current" in again.stdout


def test_an_unversioned_baseline_database_is_stamped_then_upgraded(file_app):
    upgrade(directory=MIGRATIONS, revision=BASELINE)
    _load_v2_rows(_db.engine)
    with _db.engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE alembic_version"))
    path = _db_path(file_app)
    _db.engine.dispose()

    result = _run(path)
    assert result.returncode == 0, result.stderr
    assert "stamping" in result.stdout
    check = sa.create_engine(f"sqlite:///{path}")
    with check.connect() as conn:
        assert conn.execute(sa.text("SELECT count(*) FROM holding")).scalar() == 4


def test_an_unknown_database_is_refused_not_guessed(file_app):
    with _db.engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE something_else (id INTEGER)"))
    path = _db_path(file_app)
    _db.engine.dispose()
    result = _run(path)
    assert result.returncode == 1
    assert "REFUSED" in result.stderr


def test_the_demo_seed_loads_every_side_and_passes_the_registry(tmp_path):
    path = tmp_path / "seed.db"
    env = dict(os.environ, DATABASE_URL=f"sqlite:///{path}",
               ADMIN_PASSWORD="test_password", SECRET_KEY="test_secret_key")
    for _ in range(2):              # twice: a reseed replaces, never duplicates
        result = subprocess.run([sys.executable, "scripts/seed_example.py"], cwd=ROOT, env=env,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-2000:]

    from src.holding_types import get_type, validate_attributes
    import json
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT side, type_code, attributes FROM holding")).all()
        roots = conn.execute(sa.text("SELECT count(*) FROM entity WHERE is_root = 1")).scalar()
        shares = conn.execute(sa.text("SELECT count(*) FROM beneficiary_designation")).scalar()
    assert {r.side for r in rows} == {"asset", "liability", "equity"}
    assert roots == 1 and shares >= 5
    for side, code, attrs in rows:
        assert validate_attributes(get_type(side, code), json.loads(attrs)) == [], (side, code)
