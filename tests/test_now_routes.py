"""The Now page and the timeline, end to end through the real routes: what
a person on a phone sees and what the one-tap buttons do."""

from datetime import date, timedelta

import pytest

from src.models import Entity, Event, Holding, Person, RecurringBill
from src.services import default_playbook
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


def _bill_tomorrow(db):
    tomorrow = date.today() + timedelta(days=1)
    bill = RecurringBill(holding_id=10, name="Gas and electric", payee="Utility Co",
                         amount_cents=12000, frequency="Monthly", next_due_date=tomorrow)
    db.session.add(bill)
    db.session.commit()
    return bill, f"bill:{bill.id}@{tomorrow.isoformat()}"


def _act(client, key, action, next_url="/"):
    return client.post("/manage/timeline/act", data={"key": key, "action": action, "next": next_url})


def test_now_is_the_home_page(client, estate):
    page = ok(client.get("/"))
    assert "<h1>Now</h1>" in page
    assert "Net worth overview" in page


def test_a_bill_due_tomorrow_shows_once_and_done_removes_it(client, estate):
    _, key = _bill_tomorrow(estate)
    for _ in range(2):
        page = ok(client.get("/"))
        assert page.count(f'value="{key}"') == 1
        assert "Gas and electric due" in page
    assert Event.query.filter_by(source=key).count() == 0      # reading stores nothing

    r = _act(client, key, "done")
    assert r.status_code == 302 and r.headers["Location"].endswith("/")
    for _ in range(2):
        page = ok(client.get("/"))
        assert f'value="{key}"' not in page
        title = 'class="ev-title"'
        cards = [chunk for chunk in page.split(title)[1:] if "Gas and electric due" in chunk[:200]]
        assert len(cards) == 1                                   # once, under Recently done
        assert page.index("Recently done") < page.index("Gas and electric due</a>")
    assert Event.query.filter_by(source=key).count() == 1


def test_snooze_moves_it_a_week_out(client, estate):
    _, key = _bill_tomorrow(estate)
    _act(client, key, "snooze")
    e = Event.query.filter_by(source=key).one()
    assert e.date == date.today() + timedelta(days=7) and e.done_at is None
    assert f'value="event:{e.id}"' in ok(client.get("/"))


def test_note_on_a_derived_item_opens_its_saved_event(client, estate):
    _, key = _bill_tomorrow(estate)
    r = _act(client, key, "note")
    e = Event.query.filter_by(source=key).one()
    assert f"/manage/event/{e.id}/edit" in r.headers["Location"]


def test_an_action_on_a_key_that_no_longer_applies_is_refused_kindly(client, estate):
    r = _act(client, "bill:999@2026-01-01", "done")
    assert r.status_code == 302
    assert Event.query.filter_by(source="bill:999@2026-01-01").count() == 0


def test_the_next_parameter_cannot_leave_the_app(client, estate):
    _, key = _bill_tomorrow(estate)
    r = _act(client, key, "snooze", next_url="//evil.example.com/")
    assert r.headers["Location"].endswith("/") and "evil" not in r.headers["Location"]


def test_add_an_event_from_a_holding(client, estate):
    page = ok(client.get("/holding/10"))
    assert "/manage/event/new?holding_id=10" in page
    when = date.today() + timedelta(days=3)
    r = client.post("/manage/event/new?holding_id=10", data={
        "title": "Get the roof inspected", "kind": "task", "date": when.isoformat(),
        "phase": "now", "assignee_id": 2, "holding_id": 10, "entity_id": 0, "person_id": 0,
        "repeat_every": "", "repeat_unit": "", "next": "/holding/10#events"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/holding/10#events")
    e = Event.query.filter_by(title="Get the roof inspected").one()
    assert (e.holding_id, e.assignee_id, e.date) == (10, 2, when)
    assert "Get the roof inspected" in ok(client.get("/holding/10"))
    assert "Get the roof inspected" in ok(client.get("/"))


def test_a_contact_page_offers_an_event_about_them(client, estate):
    assert "/manage/event/new?person_id=2" in ok(client.get("/contacts"))


def test_repeat_needs_both_halves(client, estate):
    r = client.post("/manage/event/new", data={
        "title": "x", "kind": "task", "phase": "now", "assignee_id": 0, "holding_id": 0,
        "entity_id": 0, "person_id": 0, "repeat_every": "2", "repeat_unit": ""})
    assert r.status_code == 200 and "Give both a number and a unit" in r.data.decode()


def test_edit_marks_done_and_spawns_the_repeat(client, estate):
    e = Event(kind="review", title="Roof check", date=date(2026, 5, 1), phase="now",
              repeat_every=6, repeat_unit="month")
    estate.session.add(e)
    estate.session.commit()
    r = client.post(f"/manage/event/{e.id}/edit", data={
        "title": "Roof check", "kind": "review", "date": "2026-05-01", "phase": "now",
        "assignee_id": 0, "holding_id": 0, "entity_id": 0, "person_id": 0,
        "repeat_every": "6", "repeat_unit": "month", "done": "y"})
    assert r.status_code == 302
    assert e.done_at == date.today()
    assert Event.query.filter_by(title="Roof check", date=date(2026, 11, 1)).count() == 1


def test_deleting_a_derived_event_closes_it_instead(client, estate):
    _, key = _bill_tomorrow(estate)
    _act(client, key, "snooze")
    e = Event.query.filter_by(source=key).one()
    client.post(f"/manage/event/{e.id}/delete")
    assert Event.query.filter_by(source=key).one().done_at == date.today()
    plain = Event(kind="task", title="plain", phase="now")
    estate.session.add(plain)
    estate.session.commit()
    client.post(f"/manage/event/{plain.id}/delete")
    assert Event.query.filter_by(title="plain").count() == 0


def test_filters_on_the_now_page(client, estate):
    when = date.today() + timedelta(days=2)
    estate.session.add_all([
        Event(kind="task", title="Tony's job", date=when, assignee_id=1, phase="now"),
        Event(kind="task", title="John's job", date=when, assignee_id=2, phase="transition"),
        Event(kind="task", title="LLC job", date=when, entity_id=2, phase="now"),
    ])
    estate.session.commit()
    page = ok(client.get("/?assignee=1"))
    assert "Tony&#39;s job" in page and "John&#39;s job" not in page
    page = ok(client.get("/?phase=transition"))
    assert "John&#39;s job" in page and "Tony&#39;s job" not in page
    page = ok(client.get("/?entity=2"))
    assert "LLC job" in page and "Tony&#39;s job" not in page


def test_overview_next_up_reads_the_real_next_event(client, estate):
    estate.session.add(Event(kind="deadline", title="File the extension",
                             date=date.today() + timedelta(days=1), phase="now"))
    estate.session.commit()
    page = ok(client.get("/overview"))
    assert "Next up" in page and "Annual Review" not in page
    # The fixture's open task from March 2026 is older, so it is the next one
    # if it is overdue; either way a real event is named.
    assert "Retitle the coupe" in page or "File the extension" in page


def test_timeline_has_history_and_filters(client, estate):
    page = ok(client.get("/timeline"))
    assert "Trust funded" in page                 # a done milestone, in history
    assert "Valued at $740,000 (Zillow)" in page  # a valuation
    assert "/holding/10" in page                  # rows link back to their record
    page = ok(client.get("/timeline?kind=valuation"))
    assert "Valued at" in page and "Retitle the coupe" not in page
    page = ok(client.get("/timeline?kind=task"))
    assert "Retitle the coupe" in page and "Valued at" not in page
    page = ok(client.get("/timeline?phase=planning"))
    assert "Trust funded" in page and "Retitle the coupe" not in page and "Valued at" not in page
    page = ok(client.get("/timeline?assignee=1"))
    assert "Retitle the coupe" in page and "Trust funded" not in page


# --- playbooks ---------------------------------------------------------------

def _default(db):
    pb = default_playbook.install(db.session)
    db.session.commit()
    return pb


def test_run_the_playbook_against_a_date(client, estate):
    pb = _default(estate)
    died = date.today() - timedelta(days=2)
    page = ok(client.get(f"/manage/playbook/{pb.id}/run?date={died.isoformat()}"))
    assert "not a substitute for legal advice" in page
    r = client.post(f"/manage/playbook/{pb.id}/run", data={"trigger_date": died.isoformat()})
    assert r.status_code == 302 and "phase=transition" in r.headers["Location"]
    made = Event.query.filter(Event.source.like(f"playbook:{pb.id}@%")).all()
    assert len(made) == len(pb.steps)
    assert {e.phase for e in made} == {"transition"}
    page = ok(client.get("/?phase=transition"))
    assert "Overdue" in page and "Get a legal pronouncement of death" in page
    # Twice on the same date adds nothing.
    client.post(f"/manage/playbook/{pb.id}/run", data={"trigger_date": died.isoformat()})
    assert Event.query.filter(Event.source.like(f"playbook:{pb.id}@%")).count() == len(pb.steps)


def test_setting_the_date_of_passing_offers_the_playbook(client, estate):
    pb = estate.session.get(type(_default(estate)), 1)   # fixture's playbook, trigger set
    r = client.post("/manage/trust/edit", data={
        "name": "The Example Family Trust", "date_established": "2014-02-09",
        "date_death_actual": "2026-10-01", "review_frequency": "Annual",
        "next_review_date": "2027-02-09", "notes": ""})
    assert r.status_code == 302
    assert f"/manage/playbook/{pb.id}/run" in r.headers["Location"]
    assert "date=2026-10-01" in r.headers["Location"]
    page = ok(client.get(r.headers["Location"]))
    assert "now has a date of passing" in page
    # Until it is run, the Now page keeps offering it.
    assert "has not been run yet" in ok(client.get("/"))


def test_edit_a_step_and_add_one(client, estate):
    r = client.post("/manage/playbook/1/step/1/edit", data={
        "offset_days": "1", "title": "Pronouncement (edited)", "kind": "task",
        "who_role": "Executor", "instructions": "x", "document_type": ""})
    assert r.status_code == 302
    page = ok(client.get("/playbook/1"))
    assert "Pronouncement (edited)" in page and "Executor" in page
    client.post("/manage/playbook/1/step/new", data={
        "offset_days": "5", "title": "New step", "kind": "deadline", "who_role": "",
        "instructions": "", "document_type": ""})
    assert "New step" in ok(client.get("/playbook/1"))


def test_a_fresh_copy_of_the_default_can_be_added(client, estate):
    r = client.post("/manage/playbook/default")
    assert r.status_code == 302
    page = ok(client.get(r.headers["Location"]))
    assert "When a trustor dies" in page and "Day 365" in page
