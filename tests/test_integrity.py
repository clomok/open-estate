"""The database refuses rows that point at nothing."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_foreign_keys_are_enforced(db):
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_an_orphan_row_is_refused(db):
    with pytest.raises(IntegrityError):
        db.session.execute(text(
            "INSERT INTO location_point (holding_id, label, latitude, longitude) "
            "VALUES (999, 'Nowhere', 0, 0)"
        ))
        db.session.flush()
    db.session.rollback()


def test_a_second_root_trust_is_refused(db):
    from src.models import Entity
    db.session.add(Entity(kind="trust", name="One", is_root=True))
    db.session.commit()
    db.session.add(Entity(kind="trust", name="Two", is_root=True))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_the_root_must_be_a_trust(db):
    from src.models import Entity
    db.session.add(Entity(kind="llc", name="Not a trust", is_root=True))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_a_holding_value_is_never_negative(db):
    from src.models import Holding
    db.session.add(Holding(side="liability", type_code="loan", name="x", value_cents=-5))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_deleting_a_person_never_erases_their_shares(db):
    from tests.fixtures_estate import _populate
    from src.models import Person, BeneficiaryDesignation
    _populate(db)
    db.session.delete(db.session.get(Person, 2))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()
    assert db.session.query(BeneficiaryDesignation).count() == 2


def test_deleting_a_holding_takes_its_sub_items_with_it(db):
    from tests.fixtures_estate import _populate
    from src.models import Holding, RecurringBill, Valuation
    _populate(db)
    db.session.delete(db.session.get(Holding, 10))
    db.session.commit()
    assert db.session.query(Valuation).count() == 0
    assert db.session.query(RecurringBill).filter_by(holding_id=10).count() == 0
    assert db.session.get(Holding, 12).secured_by_id is None    # the loan stays, unsecured
