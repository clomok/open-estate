"""Every page renders and every Phase A form does what it says, end to end
through the real routes."""

import io
from datetime import date

import pytest

from src.holding_types import REGISTRY
from src.models import BeneficiaryDesignation, Entity, Holding, Person, Valuation
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


def ok(response):
    assert response.status_code == 200, response.data[:500]
    return response.data.decode()


def test_every_page_renders(client, estate):
    pages = ["/", "/holdings", "/timeline", "/contacts", "/details", "/faq", "/settings/",
             "/manage/holding/select-type", "/manage/contact/new", "/manage/contact/edit/1",
             "/manage/trust/edit", "/manage/entity/new", "/manage/entity/2/edit"]
    pages += [f"/holding/{i}" for i in (10, 11, 12, 13, 14)]
    pages += [f"/manage/holding/edit/{i}" for i in (10, 11, 12, 13, 14)]
    pages += [f"/manage/holding/10/{kind}/new" for kind in ("structure", "location", "bill", "vendor")]
    for page in pages:
        ok(client.get(page))


def test_every_registered_type_has_a_working_form(client, estate):
    for side, code in REGISTRY:
        ok(client.get(f"/manage/holding/new/{side}/{code}"))


def test_old_asset_urls_still_land(client, estate):
    assert client.get("/assets").headers["Location"].endswith("/holdings")
    assert client.get("/asset/10").headers["Location"].endswith("/holding/10")


def test_sub_items_are_offered_on_every_side(client, estate):
    for hid in (10, 12, 13, 14):          # asset, liability, equity, custom
        page = ok(client.get(f"/holding/{hid}"))
        for kind in ("structure", "location", "bill", "vendor"):
            assert f"/manage/holding/{hid}/{kind}/new" in page


def test_dashboard_net_worth_is_assets_minus_liabilities(client, estate):
    page = ok(client.get("/"))
    # assets 750,000 + 42,000 + 5,000; liability 250,000; equity 120,000 shown apart
    assert "$547,000" in page
    assert "$120,000" in page


def test_create_an_asset_with_money_in_dollars(client, estate):
    r = client.post("/manage/holding/new/asset/real_estate", data={
        "name": "Lake Cabin", "value": "1,250,000.50", "entity_id": 0, "owner_id": 0,
        "secured_by_id": 0, "attr_address": "9 Shore Rd", "attr_purchase_date": "2001-06-01",
        "attr_purchase_price": "$300,000"})
    assert r.status_code == 302, r.data[:800]
    cabin = Holding.query.filter_by(name="Lake Cabin").one()
    assert cabin.value_cents == 125000050
    assert cabin.in_trust
    assert cabin.attributes == {"address": "9 Shore Rd", "purchase_date": "2001-06-01",
                                "purchase_price": 30000000}
    assert sorted((v.source, v.value_cents) for v in cabin.valuations) == \
        [("Initial entry", 125000050), ("Purchase", 30000000)]


def test_create_a_liability_secured_by_an_asset(client, estate):
    r = client.post("/manage/holding/new/liability/loan", data={
        "name": "HELOC", "value": "40000", "entity_id": 0, "owner_id": 0,
        "secured_by_id": 10, "attr_lender": "Example CU", "attr_interest_rate": "7.25%"})
    assert r.status_code == 302, r.data[:800]
    heloc = Holding.query.filter_by(name="HELOC").one()
    assert (heloc.side, heloc.value_cents, heloc.secured_by_id) == ("liability", 4000000, 10)
    assert heloc.attributes["interest_rate"] == 7.25


def test_a_liability_cannot_be_secured_by_another_liability(client, estate):
    r = client.post("/manage/holding/new/liability/loan", data={
        "name": "Bad", "value": "1", "entity_id": 0, "owner_id": 0, "secured_by_id": 12})
    assert r.status_code == 200
    assert not Holding.query.filter_by(name="Bad").first()


def test_create_equity_with_ownership(client, estate):
    r = client.post("/manage/holding/new/equity/business_shares", data={
        "name": "Example Corp shares", "value": "80000", "entity_id": 2, "owner_id": 1,
        "secured_by_id": 0, "ownership_pct": "25", "attr_shares_held": "1,000"})
    assert r.status_code == 302, r.data[:800]
    h = Holding.query.filter_by(name="Example Corp shares").one()
    assert (h.side, h.ownership_pct, h.entity_id) == ("equity", 25.0, 2)
    assert h.attributes["shares_held"] == 1000


def test_custom_type_fields_are_named_by_the_user(client, estate):
    r = client.post("/manage/holding/new/liability/custom", data={
        "name": "Loan from Aunt May", "value": "5000", "entity_id": 0, "owner_id": 0,
        "secured_by_id": 0, "custom_type_label": "Family IOU",
        "custom_name": ["Lender", "Terms", ""], "custom_value": ["Aunt May", "No interest", "x"]})
    assert r.status_code == 302, r.data[:800]
    h = Holding.query.filter_by(name="Loan from Aunt May").one()
    assert h.type_label == "Family IOU"
    assert h.attributes["fields"] == [{"name": "Lender", "value": "Aunt May"},
                                      {"name": "Terms", "value": "No interest"}]
    assert "Aunt May" in ok(client.get(f"/holding/{h.id}"))


def test_an_invalid_detail_is_refused(client, estate):
    r = client.post("/manage/holding/new/liability/loan", data={
        "name": "Typo", "value": "100", "entity_id": 0, "owner_id": 0,
        "secured_by_id": 0, "attr_interest_rate": "lots"})
    assert r.status_code == 200 and b"not a number" in r.data
    assert not Holding.query.filter_by(name="Typo").first()


def test_a_negative_value_is_refused(client, estate):
    r = client.post("/manage/holding/new/liability/loan", data={
        "name": "Neg", "value": "-100", "entity_id": 0, "owner_id": 0, "secured_by_id": 0})
    assert r.status_code == 200
    assert not Holding.query.filter_by(name="Neg").first()


def test_edit_records_a_valuation_when_the_value_changes(client, estate):
    r = client.post("/manage/holding/edit/11", data={
        "name": "1969 Coupe", "value": "45000", "entity_id": 2, "owner_id": 1,
        "secured_by_id": 0, "attr_vin": "EXAMPLE123"})
    assert r.status_code == 302
    car = estate.session.get(Holding, 11)
    assert car.value_cents == 4500000
    assert [(v.source, v.value_cents) for v in car.valuations] == [("Manual update", 4500000)]


def test_changing_type_keeps_unmatched_details_in_notes(client, estate):
    r = client.post("/manage/holding/edit/12?type=loan", data={
        "name": "Home Mortgage", "value": "250000", "entity_id": 0, "owner_id": 0,
        "secured_by_id": 10, "attr_lender": "Example Bank", "attr_interest_rate": "3.5"})
    assert r.status_code == 302
    m = estate.session.get(Holding, 12)
    assert m.type_code == "loan"
    assert m.attributes == {"lender": "Example Bank", "interest_rate": 3.5}


def test_the_trust_is_the_default_holder_and_is_stored_as_null(client, estate):
    page = ok(client.get("/manage/holding/new/asset/other"))
    assert '<option selected value="0">The Example Family Trust (the trust)</option>' in page
    r = client.post("/manage/holding/new/asset/other", data={
        "name": "Piano", "value": "3000", "entity_id": 0, "owner_id": 0, "secured_by_id": 0})
    assert r.status_code == 302
    assert Holding.query.filter_by(name="Piano").one().entity_id is None


def test_valuation_add_edit_delete_moves_the_value(client, estate):
    client.post("/manage/holding/10/valuation", data={
        "date": "2026-10-01", "value": "800,000", "source": "Appraiser"})
    house = estate.session.get(Holding, 10)
    assert house.value_cents == 80000000
    newest = Valuation.query.filter_by(source="Appraiser").one()
    client.post(f"/manage/valuation/{newest.id}/edit", data={
        "date": "2026-10-01", "value": "810000.25", "source": "Appraiser"})
    assert estate.session.get(Holding, 10).value_cents == 81000025
    client.post(f"/manage/valuation/{newest.id}/delete")
    assert estate.session.get(Holding, 10).value_cents == 74000000   # back to the 2025 Zillow value


def test_beneficiary_shares_add_edit_remove(client, estate):
    # Car has no shares yet.
    r = client.post("/manage/holding/11/designation", data={
        "person_id": 2, "percentage": "60", "kind": "will", "notes": ""})
    assert r.status_code == 302
    page = ok(client.get("/holding/11"))
    assert "40% not yet assigned" in page

    client.post("/manage/holding/11/designation", data={
        "person_id": 1, "percentage": "40", "kind": "will"})
    assert estate.session.get(Holding, 11).share_totals() == {"will": 100}
    assert "Complete" in ok(client.get("/holding/11"))

    # The same person, same kind, again: refused, not duplicated.
    client.post("/manage/holding/11/designation", data={
        "person_id": 1, "percentage": "5", "kind": "will"})
    assert BeneficiaryDesignation.query.filter_by(holding_id=11).count() == 2

    d = BeneficiaryDesignation.query.filter_by(holding_id=11, person_id=2).one()
    client.post(f"/manage/designation/{d.id}/edit", data={
        "person_id": 2, "percentage": "70", "kind": "will"})
    assert "Over-assigned by 10%" in ok(client.get("/holding/11"))

    client.post(f"/manage/designation/{d.id}/delete")
    assert BeneficiaryDesignation.query.filter_by(holding_id=11).count() == 1


def test_mark_verified(client, estate):
    client.post("/manage/holding/10/verify")
    client.post("/manage/contact/2/verify")
    assert estate.session.get(Holding, 10).last_verified == date.today()
    assert estate.session.get(Person, 2).last_verified == date.today()


def test_a_person_can_hold_several_roles(client, estate):
    r = client.post("/manage/contact/new", data={
        "name": "Sam Spouse", "kind": "individual",
        "roles": ["Trustee", "Beneficiary"], "email": "sam@example.com"})
    assert r.status_code == 302
    sam = Person.query.filter_by(name="Sam Spouse").one()
    assert sam.role_codes == ["Trustee", "Beneficiary"]
    page = ok(client.get("/contacts"))
    assert "Trustee" in page and "Beneficiary" in page

    client.post(f"/manage/contact/edit/{sam.id}", data={
        "name": "Sam Spouse", "kind": "individual", "roles": ["Beneficiary"]})
    assert estate.session.get(Person, sam.id).role_codes == ["Beneficiary"]


def test_deleting_a_beneficiary_is_refused_while_they_have_shares(client, estate):
    client.get("/manage/contact/delete/2")
    assert estate.session.get(Person, 2) is not None


def test_trust_page_edits_the_root_entity(client, estate):
    r = client.post("/manage/trust/edit", data={
        "name": "Renamed Trust", "review_frequency": "Quarterly",
        "next_review_date": "2027-01-01"})
    assert r.status_code == 302
    root = Entity.query.filter_by(is_root=True).one()
    assert (root.name, root.review_frequency) == ("Renamed Trust", "Quarterly")
    assert "Renamed Trust" in ok(client.get("/details"))


def test_add_on_entities(client, estate):
    r = client.post("/manage/entity/new", data={
        "kind": "corporation", "name": "Example Corp", "person_id": 0})
    assert r.status_code == 302
    corp = Entity.query.filter_by(name="Example Corp").one()
    assert (corp.is_root, corp.parent_id) == (False, 1)
    assert "Example Corp" in ok(client.get("/details"))

    # An entity that still holds things is not removed.
    client.post("/manage/entity/2/delete")
    assert estate.session.get(Entity, 2) is not None
    client.post(f"/manage/entity/{corp.id}/delete")
    assert estate.session.get(Entity, corp.id) is None
    client.post("/manage/entity/1/delete")
    assert estate.session.get(Entity, 1) is not None


def test_a_fresh_install_gets_its_root_trust(client, db):
    ok(client.get("/details"))
    assert Entity.query.filter_by(is_root=True, kind="trust").count() == 1


def test_backup_download_and_upload_through_settings(client, estate):
    r = client.get("/settings/download")
    assert r.status_code == 200
    client.post("/manage/holding/10/verify")    # change something after the backup
    r = client.post("/settings/upload", data={
        "backup_file": (io.BytesIO(r.data), "estate_backup.zip")},
        content_type="multipart/form-data")
    assert r.status_code == 302
    assert estate.session.get(Holding, 10).last_verified is None
    assert Holding.query.count() == 5
