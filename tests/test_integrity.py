"""The database refuses rows that point at nothing."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_foreign_keys_are_enforced(db):
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_an_orphan_row_is_refused(db):
    with pytest.raises(IntegrityError):
        db.session.execute(text(
            "INSERT INTO location_point (asset_id, label, latitude, longitude) "
            "VALUES (999, 'Nowhere', 0, 0)"
        ))
        db.session.flush()
    db.session.rollback()
