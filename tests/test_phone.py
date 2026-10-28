"""Phone numbers display and save as (xxx) xxx-xxxx; anything that is not a
ten-digit US number is kept exactly as typed."""

import pytest

from src.phone import format_phone


@pytest.mark.parametrize("raw, shown", [
    ("5551234567", "(555) 123-4567"),
    ("555-123-4567", "(555) 123-4567"),
    ("555.123.4567", "(555) 123-4567"),
    ("(555)123-4567", "(555) 123-4567"),
    ("+1 555 123 4567", "(555) 123-4567"),
    ("15551234567", "(555) 123-4567"),
    ("555-0100", "555-0100"),
    ("555-123-4567 ext 12", "555-123-4567 ext 12"),
    ("+44 20 7946 0958", "+44 20 7946 0958"),
    ("", ""),
    (None, None),
])
def test_format_phone(raw, shown):
    assert format_phone(raw) == shown


def test_phone_filter_registered(app):
    assert app.jinja_env.filters["phone"]("5551234567") == "(555) 123-4567"


def test_a_saved_contact_stores_and_shows_the_formatted_number(app, db):
    from src.models import Person
    client = app.test_client()
    with client.session_transaction() as s:
        s["is_admin"] = True
    r = client.post("/e/test/manage/contact/new",
                    data={"name": "Pat Phone", "kind": "individual",
                          "roles": ["Trustee"], "phone": "555.123.4567"})
    assert r.status_code == 302, r.data[:300]
    assert Person.query.filter_by(name="Pat Phone").one().phone == "(555) 123-4567"
    assert "(555) 123-4567" in client.get("/e/test/contacts").data.decode()
