"""The input forms and the checks behind them refuse what they should, accept
what they should, and never answer a bad value with a 500."""

import io
import json
import math
import os
from datetime import date, timedelta

import pytest

from src.holding_types import get_type, parse_field, validate_attributes
from src.models import (BeneficiaryDesignation, Entity, Event, Holding, LocationPoint,
                        Person, PropertyStructure, Valuation)
from src.money import to_cents
from src.services import events as event_service
from tests.fixtures_estate import _populate


@pytest.fixture
def client(app, db):
    c = app.test_client()
    with c.session_transaction() as s:
        s["is_admin"] = True
    return c


@pytest.fixture
def estate(db):
    _populate(db)
    return db


# --- the parsers --------------------------------------------------------------

def test_an_absurd_amount_is_refused_not_overflowed():
    with pytest.raises(ValueError):
        to_cents("1e30")
    assert to_cents("10,000,000") == 1_000_000_000


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf", "1e400"])
def test_a_number_field_refuses_nan_and_infinity(raw):
    field = get_type("liability", "mortgage").field("payment_due_day")
    with pytest.raises(ValueError):
        parse_field(field, raw)


def test_stored_attributes_are_range_checked_too():
    mortgage = get_type("liability", "mortgage")
    assert validate_attributes(mortgage, {"interest_rate": 6.5}) == []
    assert validate_attributes(mortgage, {"interest_rate": 650}) != []
    assert validate_attributes(mortgage, {"interest_rate": float("nan")}) != []


# --- the forms, through the routes ------------------------------------------------

def test_a_zero_valuation_is_allowed(client, estate):
    client.post("/e/test/manage/holding/11/valuation",
                data={"date": "2026-01-02", "value": "0", "source": "Written off"})
    assert estate.session.get(Holding, 11).value_cents == 0
    assert Valuation.query.filter_by(holding_id=11, source="Written off").count() == 1


def test_a_pin_on_the_equator_is_allowed_and_off_the_globe_is_not(client, estate):
    client.post("/e/test/manage/holding/10/location/new",
                data={"label": "Null Island", "latitude": "0", "longitude": "0"})
    assert LocationPoint.query.filter_by(label="Null Island").count() == 1
    for lat, lon in (("91", "0"), ("0", "181"), ("nan", "0")):
        client.post("/e/test/manage/holding/10/location/new",
                    data={"label": f"Bad {lat} {lon}", "latitude": lat, "longitude": lon})
        assert LocationPoint.query.filter_by(label=f"Bad {lat} {lon}").count() == 0


def test_a_nan_share_is_refused(client, estate):
    before = BeneficiaryDesignation.query.count()
    client.post("/e/test/manage/holding/11/designation",
                data={"person_id": 1, "percentage": "nan", "kind": "trust_schedule"})
    assert BeneficiaryDesignation.query.count() == before


def test_a_huge_holding_value_is_a_form_error_not_a_crash(client, estate):
    r = client.post("/e/test/manage/holding/edit/11",
                    data={"name": "1969 Coupe", "value": "1e30", "entity_id": 0,
                          "owner_id": 0, "secured_by_id": 0})
    assert r.status_code == 200
    assert b"too large" in r.data


def test_a_future_date_of_passing_is_refused(client, estate):
    root = Entity.query.filter_by(is_root=True).one()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/e/test/manage/trust/edit",
                    data={"name": root.name, "date_death_actual": tomorrow,
                          "review_frequency": "Annual"})
    assert r.status_code == 200
    assert estate.session.get(Entity, root.id).date_death_actual is None


# --- deletes are POST only ----------------------------------------------------------

def test_deletes_do_not_run_on_a_get(client, estate):
    structure = PropertyStructure(holding_id=10, name="Shed")
    estate.session.add(structure)
    estate.session.commit()
    for url in ("/e/test/manage/holding/delete/11", "/e/test/manage/contact/delete/3",
                f"/e/test/manage/holding/10/structure/{structure.id}/delete"):
        assert client.get(url).status_code == 405
    assert estate.session.get(Holding, 11) is not None
    assert estate.session.get(Person, 3) is not None
    client.post(f"/e/test/manage/holding/10/structure/{structure.id}/delete")
    assert estate.session.get(PropertyStructure, structure.id) is None


# --- the timeline -------------------------------------------------------------------

def test_a_bad_row_key_is_not_found_not_a_crash(client, estate):
    r = client.post("/e/test/manage/timeline/act", data={"key": "event:abc", "action": "done"})
    assert r.status_code == 302


def test_a_bad_assignee_filter_shows_nothing_not_a_crash(client, estate):
    assert client.get("/e/test/?assignee=abc").status_code == 200
    assert client.get("/e/test/timeline?assignee=abc").status_code == 200


def test_done_reopen_done_does_not_duplicate_the_next_occurrence(estate):
    event_service.complete("event:31")
    event_service.reopen("event:31")
    event_service.complete("event:31")
    estate.session.commit()
    assert Event.query.filter_by(title="Annual trust review").count() == 2


@pytest.mark.parametrize("nxt", ["//evil.example/", "/\\evil.example/", "https://evil.example/",
                                 "/\t/evil.example/"])
def test_next_never_leaves_the_app(client, estate, nxt):
    r = client.post("/e/test/manage/timeline/act",
                    data={"key": "event:30", "action": "snooze", "next": nxt})
    assert r.headers["Location"].endswith("/e/test/")


# --- restore ------------------------------------------------------------------------

def test_a_damaged_zip_is_refused_politely(client, estate):
    r = client.post("/e/test/settings/upload",
                    data={"backup_file": (io.BytesIO(b"not a zip"), "backup.ZIP")},
                    content_type="multipart/form-data")
    assert r.status_code == 302
    assert estate.session.get(Holding, 10) is not None


def test_restore_refuses_a_holding_with_a_bad_detail(client, estate):
    from src.services.export_service import generate_backup_zip
    import zipfile
    with zipfile.ZipFile(generate_backup_zip()) as z:
        name = next(n for n in z.namelist() if n.endswith(".json"))
        data = json.loads(z.read(name))
    house = next(h for h in data["holdings"] if h["id"] == 10)
    house["attributes"] = {"purchase_price": "$1,200"}
    client.post("/e/test/settings/upload",
                data={"backup_file": (io.BytesIO(json.dumps(data).encode()), "b.json")},
                content_type="multipart/form-data")
    # Refused whole: the estate is as it was.
    assert estate.session.get(Holding, 10).attributes != {"purchase_price": "$1,200"}


# --- CSRF is enforced on every POST -------------------------------------------------

def test_a_post_without_a_token_is_refused(tmp_path):
    from flask import g
    from tests.conftest import make_app
    from src.extensions import db as _db
    application = make_app(tmp_path)
    application.config["WTF_CSRF_ENABLED"] = True
    with application.app_context():
        g.estate = "test"
        _db.create_all()
        _populate(_db)
        c = application.test_client()
        with c.session_transaction() as s:
            s["is_admin"] = True
        r = c.post("/e/test/manage/holding/delete/11")
        assert r.status_code == 303
        assert _db.session.get(Holding, 11) is not None
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()


# --- contacts -----------------------------------------------------------------------

def test_role_checkboxes_are_not_each_required(client, estate):
    # A `required` on every box makes the browser demand all of them ticked.
    html = client.get("/e/test/manage/contact/new").data.decode()
    assert 'type="checkbox"' in html
    assert not any("required" in tag for tag in html.split("<input") if 'name="roles"' in tag)


def test_a_contact_with_one_role_saves_and_with_none_does_not(client, estate):
    client.post("/e/test/manage/contact/new",
                data={"name": "Una Role", "kind": "individual", "roles": ["Attorney"]})
    assert Person.query.filter_by(name="Una Role").one().role_codes == ["Attorney"]
    r = client.post("/e/test/manage/contact/new", data={"name": "No Role", "kind": "individual"})
    assert b"Pick at least one role." in r.data
    assert Person.query.filter_by(name="No Role").count() == 0
