"""The timeline engine: derived feeds, the actions on them, repeats and
playbook runs.

The promise the feeds make: an item is computed, never stored, until someone
touches it; then it is stored exactly once and the feed stops offering it.
"""

from datetime import date, timedelta

import pytest

from src.models import (BeneficiaryDesignation, Entity, Event, Holding, Person,
                        Playbook, RecurringBill)
from src.services import default_playbook, events, feeds, playbooks
from src.services.dates import add_interval
from src.services.estate import get_root_entity

TODAY = date(2026, 10, 15)


@pytest.fixture
def ctx(app, db):
    with app.test_request_context():
        yield db


def _house(db, **kw):
    h = Holding(side="asset", type_code="real_estate", name="House", value_cents=100,
                last_verified=TODAY, **kw)
    db.session.add(h)
    db.session.flush()
    db.session.add(BeneficiaryDesignation(holding_id=h.id, person_id=_person(db).id,
                                          percentage=100, kind="trust_schedule"))
    db.session.flush()
    return h


def _person(db, **kw):
    p = Person.query.filter_by(name=kw.get("name", "Heir")).first()
    if p is None:
        p = Person(name=kw.pop("name", "Heir"), email=kw.pop("email", "heir@example.com"), **kw)
        db.session.add(p)
        db.session.flush()
    return p


def _keys(rows):
    return [r.key for r in rows]


def _bill(db, due, frequency="Monthly"):
    house = _house(db)
    bill = RecurringBill(holding_id=house.id, name="Water", payee="City",
                         amount_cents=8500, frequency=frequency, next_due_date=due)
    db.session.add(bill)
    db.session.commit()
    return bill


# --- the bill due tomorrow ----------------------------------------------------

def test_a_bill_due_tomorrow_appears_once_in_this_week(ctx):
    bill = _bill(ctx, TODAY + timedelta(days=1))
    key = f"bill:{bill.id}@{(TODAY + timedelta(days=1)).isoformat()}"

    rows = events.all_rows(TODAY)
    assert _keys(rows).count(key) == 1
    sections = events.now_sections(rows, TODAY)
    assert _keys(sections["week"]) == [key]
    assert not sections["overdue"] and not sections["month"]


def test_reading_never_stores_anything_and_never_duplicates(ctx):
    bill = _bill(ctx, TODAY + timedelta(days=1))
    key = f"bill:{bill.id}@{bill.next_due_date.isoformat()}"
    for _ in range(3):                                   # three page loads
        rows = events.all_rows(TODAY)
        assert _keys(rows).count(key) == 1
    assert Event.query.count() == 0


def test_marking_the_bill_done_removes_it_and_moves_the_bill_on(ctx):
    bill = _bill(ctx, TODAY + timedelta(days=1))
    due = bill.next_due_date
    key = f"bill:{bill.id}@{due.isoformat()}"

    event, spawned = events.complete(key, TODAY)
    ctx.session.commit()
    assert spawned is None
    assert (event.source, event.done_at, event.kind) == (key, TODAY, "deadline")
    assert bill.next_due_date == add_interval(due, 1, "month")

    for _ in range(2):                                   # and it stays gone on reload
        rows = events.all_rows(TODAY)
        assert key not in _keys(rows)
        sections = events.now_sections(rows, TODAY)
        assert [r.title for r in sections["week"]] == []
        assert [r.key for r in sections["recent"]] == [f"event:{event.id}"]
    assert Event.query.filter_by(source=key).count() == 1

    # Next month's bill is a new key and shows up by itself.
    nxt = f"bill:{bill.id}@{bill.next_due_date.isoformat()}"
    assert nxt in _keys(events.all_rows(TODAY))


def test_completing_twice_does_not_move_the_bill_twice(ctx):
    bill = _bill(ctx, TODAY + timedelta(days=1))
    key = f"bill:{bill.id}@{bill.next_due_date.isoformat()}"
    events.complete(key, TODAY)
    once = bill.next_due_date
    events.complete(key, TODAY)
    assert bill.next_due_date == once
    assert Event.query.count() == 1


def test_a_bill_with_no_regular_frequency_stays_done(ctx):
    bill = _bill(ctx, TODAY - timedelta(days=3), frequency="Other")
    key = f"bill:{bill.id}@{bill.next_due_date.isoformat()}"
    assert _keys(events.now_sections(events.all_rows(TODAY), TODAY)["overdue"]) == [key]
    events.complete(key, TODAY)
    assert bill.next_due_date == TODAY - timedelta(days=3)
    assert key not in _keys(events.all_rows(TODAY))


# --- flags --------------------------------------------------------------------

def test_a_contact_with_no_phone_or_email_needs_attention_until_snoozed(ctx):
    p = Person(name="Cousin Ed")
    ctx.session.add(p)
    ctx.session.commit()
    key = f"contact:person:{p.id}"
    assert key in _keys(events.now_sections(events.all_rows(TODAY), TODAY)["attention"])

    event = events.snooze(key, today=TODAY)
    ctx.session.commit()
    assert event.date == TODAY + timedelta(days=7)
    sections = events.now_sections(events.all_rows(TODAY), TODAY)
    assert key not in _keys(sections["attention"])
    assert f"event:{event.id}" in _keys(sections["week"])


def test_a_holding_nobody_has_verified_comes_back_after_verifying_lapses(ctx):
    h = _house(ctx)
    h.last_verified = TODAY - timedelta(days=400)
    ctx.session.commit()
    key = f"verify:holding:{h.id}@{h.last_verified.isoformat()}"
    assert key in _keys(events.all_rows(TODAY))

    events.complete(key, TODAY)
    ctx.session.commit()
    assert h.last_verified == TODAY
    assert not [k for k in _keys(events.all_rows(TODAY)) if k.startswith("verify:")]
    # A year on it is stale again, under a new key.
    later = TODAY + timedelta(days=366)
    assert f"verify:holding:{h.id}@{TODAY.isoformat()}" in _keys(events.all_rows(later))


def test_verify_window_is_per_type(ctx):
    h = _house(ctx)
    h.last_verified = TODAY - timedelta(days=100)
    ctx.session.commit()
    assert not [k for k in _keys(events.all_rows(TODAY)) if k.startswith("verify:")]


def test_beneficiary_gaps(ctx):
    h = _house(ctx)
    lone = Holding(side="asset", type_code="bank", name="Checking", last_verified=TODAY)
    debt = Holding(side="liability", type_code="loan", name="Loan", last_verified=TODAY)
    ctx.session.add_all([lone, debt])
    ctx.session.commit()
    keys = _keys(events.all_rows(TODAY))
    assert f"shares:holding:{lone.id}@none" in keys
    assert not [k for k in keys if k.startswith(f"shares:holding:{debt.id}")]
    assert not [k for k in keys if k.startswith(f"shares:holding:{h.id}")]

    h.beneficiary_designations[0].percentage = 90
    ctx.session.commit()
    gap = [r for r in events.all_rows(TODAY) if r.key.startswith(f"shares:holding:{h.id}")]
    assert [r.key for r in gap] == [f"shares:holding:{h.id}@trust_schedule=90"]
    assert "90%" in gap[0].title


def test_holdings_in_a_company_need_no_beneficiary_of_their_own(ctx):
    root = get_root_entity()
    llc = Entity(kind="llc", name="Rentals LLC", parent_id=root.id)
    ctx.session.add(llc)
    ctx.session.flush()
    ctx.session.add(Holding(side="asset", type_code="real_estate", name="Duplex",
                            entity_id=llc.id, last_verified=TODAY))
    ctx.session.commit()
    assert not [k for k in _keys(events.all_rows(TODAY)) if k.startswith("shares:")]


def test_the_trust_review_is_dated_and_reschedules(ctx):
    root = get_root_entity()
    root.next_review_date = TODAY + timedelta(days=20)
    root.review_frequency = "Annual"
    ctx.session.commit()
    key = f"review:entity:{root.id}@{root.next_review_date.isoformat()}"
    assert _keys(events.now_sections(events.all_rows(TODAY), TODAY)["month"]) == [key]
    events.complete(key, TODAY)
    assert root.next_review_date == add_interval(TODAY + timedelta(days=20), 1, "year")
    assert root.last_verified == TODAY


def test_every_feed_has_a_unique_prefix_and_resolves_its_own_keys(ctx):
    assert len({f.prefix for f in feeds.FEEDS}) == len(feeds.FEEDS)
    _bill(ctx, TODAY)
    ctx.session.add(Person(name="No Contact"))
    ctx.session.commit()
    for item in feeds.derived_items(TODAY):
        assert feeds.feed_for(item.source).name == item.feed
        assert feeds.find(item.source, TODAY) == item


# --- stored events ------------------------------------------------------------

def test_a_repeating_event_spawns_the_next_one_when_done(ctx):
    e = Event(kind="review", title="Look at the roof", date=date(2026, 1, 31),
              repeat_every=1, repeat_unit="month", phase="now")
    ctx.session.add(e)
    ctx.session.commit()
    done, nxt = events.complete(f"event:{e.id}", TODAY)
    assert done.done_at == TODAY
    assert (nxt.date, nxt.repeat_every, nxt.done_at) == (date(2026, 2, 28), 1, None)


def test_filters(ctx):
    root = get_root_entity()
    a = _person(ctx, name="Alice")
    ctx.session.add_all([
        Event(kind="task", title="mine", date=TODAY, assignee_id=a.id, phase="now"),
        Event(kind="deadline", title="later", date=TODAY, phase="transition"),
    ])
    ctx.session.commit()
    rows = [r for r in events.all_rows(TODAY) if not r.derived]
    assert [r.title for r in events.apply_filters(rows, assignee=str(a.id))] == ["mine"]
    assert [r.title for r in events.apply_filters(rows, assignee="none")] == ["later"]
    assert [r.title for r in events.apply_filters(rows, phases=["transition"])] == ["later"]
    assert [r.title for r in events.apply_filters(rows, kinds=["task"])] == ["mine"]
    assert len(events.apply_filters(rows, entity=root.id)) == 2


def test_add_interval_clamps_to_the_end_of_the_month():
    assert add_interval(date(2026, 1, 31), 1, "month") == date(2026, 2, 28)
    assert add_interval(date(2024, 2, 29), 1, "year") == date(2025, 2, 28)
    assert add_interval(date(2026, 11, 15), 3, "month") == date(2027, 2, 15)
    assert add_interval(date(2026, 1, 1), 2, "week") == date(2026, 1, 15)


# --- playbooks ----------------------------------------------------------------

def test_the_default_playbook_installs_with_every_step(ctx):
    pb = default_playbook.install(ctx.session)
    ctx.session.commit()
    assert pb.trigger == "death_of_trustor"
    assert len(pb.steps) == len(default_playbook.STEPS)
    offsets = [s.offset_days for s in pb.steps]
    assert offsets == sorted(offsets) and offsets[0] == 0 and offsets[-1] == 365
    assert playbooks.death_playbook().id == pb.id


def test_running_a_playbook_makes_one_event_per_step(ctx):
    trustee = Person(name="Junior", email="j@example.com")
    trustee.set_roles(["SuccessorTrustee"])
    ctx.session.add(trustee)
    pb = default_playbook.install(ctx.session)
    ctx.session.commit()
    died = date(2026, 3, 1)

    created, skipped = playbooks.run(pb, died)
    ctx.session.commit()
    assert (len(created), skipped) == (len(pb.steps), 0)
    assert {e.phase for e in created} == {"transition"}
    first = created[0]
    assert first.date == died and first.assignee_id == trustee.id
    assert "Find first: Advance directive / POLST" in first.description
    tax = next(e for e in created if "706" in e.title)
    assert (tax.kind, tax.date) == ("deadline", died + timedelta(days=270))
    # A step whose role nobody holds is left unassigned, not given to someone.
    assert next(e for e in created if e.title == "Meet the estate attorney").assignee_id is None
    assert playbooks.runs(pb) == [(died.isoformat(), len(pb.steps))]


def test_running_the_same_playbook_twice_on_one_date_adds_nothing(ctx):
    pb = default_playbook.install(ctx.session)
    ctx.session.commit()
    playbooks.run(pb, date(2026, 3, 1))
    ctx.session.commit()
    created, skipped = playbooks.run(pb, date(2026, 3, 1))
    assert (created, skipped) == ([], len(pb.steps))
    assert Event.query.count() == len(pb.steps)


def test_playbook_events_land_on_the_now_page(ctx):
    pb = default_playbook.install(ctx.session)
    ctx.session.commit()
    playbooks.run(pb, TODAY)
    ctx.session.commit()
    sections = events.now_sections(events.all_rows(TODAY), TODAY)
    week_titles = [r.title for r in sections["week"]]
    assert "Get a legal pronouncement of death" in week_titles
    assert "Notify Social Security" in week_titles          # day 7
    assert not sections["overdue"]
