"""Derived feeds: things the binder can work out for itself that need doing.

A bill's next due date, the trust's review date, a holding nobody has checked
in a year, a contact with no way to reach them, an asset with no one named
to inherit it. None of these are typed in as events. They are computed at
read time, every time, from the records they are about.

Each derived item has a `source` key, e.g. `bill:42@2026-11-01`. The moment
someone touches one (done, snooze, a note) it becomes exactly one stored
Event carrying that source, and from then on the feed skips it, because the
database refuses a second row with the same source (uq_event_source).

The key carries the cycle it is about after the `@`: the due date of this
bill, the last time this holding was verified. When the bill is paid its
next due date moves on, so next month's bill is a different key and shows up
by itself; when a holding is verified, the next time it goes stale is a new
key too. A flag with no cycle (a contact with no phone or email) stays
dismissed once dismissed.

Adding a feed is one Feed(...) in FEEDS. Phase C adds document review and
policy renewal here.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Optional

from flask import url_for

from src.extensions import db
from src.models import (BeneficiaryDesignation, Entity, Event, Holding, Person,
                        RecurringBill, Valuation)
from src.money import format_cents
from src.services.dates import add_interval

# Assets and equity inherited through these holders need someone named.
# A holding inside an LLC or corporation passes with the company itself.
_NEEDS_BENEFICIARY = (None, "individual", "retirement_account", "trust")


@dataclass
class DerivedItem:
    source: str
    feed: str
    kind: str
    title: str
    date: Optional[date]           # None = "needs attention", no due date
    phase: str = "now"
    description: str = ""
    link: str = "#"
    holding_id: Optional[int] = None
    entity_id: Optional[int] = None
    person_id: Optional[int] = None


@dataclass
class Feed:
    name: str
    prefix: str                    # the part of the source before the first ":"
    label: str
    items: Callable[[date], list]
    # Run when the item is marked done: move the record on to its next
    # cycle (a bill's next due date, a verified stamp). None = acknowledge.
    on_done: Optional[Callable[[str, date], None]] = None
    help: str = ""


def _id(source):
    """`bill:42@2026-11-01` -> 42; `verify:holding:7@never` -> 7."""
    return int(source.split("@", 1)[0].rsplit(":", 1)[1])


def _holding_link(h, tab=None):
    return url_for("main.holding_details", id=h.id) + (f"#{tab}" if tab else "")


# --- bills -----------------------------------------------------------------

_BILL_STEP = {"Monthly": (1, "month"), "Quarterly": (3, "month"), "Annual": (1, "year")}


def _bill_items(today):
    out = []
    for b in RecurringBill.query.filter(RecurringBill.next_due_date.isnot(None)):
        bits = [b.payee or "", f"~{format_cents(b.amount_cents)}" if b.amount_cents else ""]
        if b.is_autopay:
            bits.append("autopay - check it went through")
        out.append(DerivedItem(
            source=f"bill:{b.id}@{b.next_due_date.isoformat()}", feed="bills",
            kind="deadline", title=f"{b.name} due", date=b.next_due_date,
            description=" · ".join(x for x in bits if x),
            link=_holding_link(b.holding, "bills"), holding_id=b.holding_id))
    return out


def _bill_done(source, today):
    bill = db.session.get(RecurringBill, _id(source))
    if bill is None or bill.next_due_date is None:
        return
    due = date.fromisoformat(source.split("@", 1)[1])
    step = _BILL_STEP.get(bill.frequency or "")
    # Only move the bill on if it still says the date that was paid.
    if step and bill.next_due_date == due:
        bill.next_due_date = add_interval(due, *step)


# --- the trust's review ----------------------------------------------------

_REVIEW_STEP = {"Annual": (1, "year"), "Quarterly": (3, "month")}


def _review_items(today):
    out = []
    for e in Entity.query.filter(Entity.next_review_date.isnot(None)):
        out.append(DerivedItem(
            source=f"review:entity:{e.id}@{e.next_review_date.isoformat()}", feed="reviews",
            kind="review", title=f"Review {e.name}", date=e.next_review_date,
            phase="planning",
            description=f"{e.review_frequency or 'Scheduled'} review: read the trust, "
                        "check trustees, beneficiaries and holdings are still right.",
            link=url_for("main.details_view"), entity_id=e.id))
    return out


def _review_done(source, today):
    entity = db.session.get(Entity, _id(source))
    if entity is None:
        return
    due = date.fromisoformat(source.split("@", 1)[1])
    entity.mark_verified(today)
    step = _REVIEW_STEP.get(entity.review_frequency or "")
    if step and entity.next_review_date == due:
        entity.next_review_date = add_interval(due, *step)


# --- holdings nobody has checked -------------------------------------------

def _since(stamp):
    return stamp.date() if hasattr(stamp, "date") else stamp


def _verify_items(today):
    out = []
    for h in Holding.query.all():
        days = h.htype.verify_days if h.htype else 365
        last = h.last_verified or _since(h.created_at)
        if last is None or last + timedelta(days=days) > today:
            continue
        when = h.last_verified.isoformat() if h.last_verified else "never"
        said = (f"Last verified {h.last_verified.isoformat()}" if h.last_verified
                else "Never verified")
        out.append(DerivedItem(
            source=f"verify:holding:{h.id}@{when}", feed="verify", kind="review",
            title=f"Check {h.name} is still right", date=None,
            description=f"{said}. Open it, confirm the details, press Mark verified.",
            link=_holding_link(h), holding_id=h.id))
    return out


def _verify_done(source, today):
    h = db.session.get(Holding, _id(source))
    if h is not None:
        h.mark_verified(today)


# --- values that have gone stale -------------------------------------------

def _value_items(today):
    out = []
    latest = dict(db.session.query(Valuation.holding_id, db.func.max(Valuation.date))
                  .group_by(Valuation.holding_id).all())
    for h in Holding.query.all():
        days = h.htype.revalue_days if h.htype else 365
        last = latest.get(h.id)
        since = last or _since(h.created_at)
        if since is None or since + timedelta(days=days) > today:
            continue
        said = f"Last valued {last.isoformat()}" if last else "Never valued"
        out.append(DerivedItem(
            source=f"value:holding:{h.id}@{last.isoformat() if last else 'never'}",
            feed="values", kind="review", title=f"Update the value of {h.name}",
            date=None, description=f"{said}. Add a valuation from a statement or estimate.",
            link=_holding_link(h), holding_id=h.id))
    return out


# --- people you could not reach --------------------------------------------

def _contact_items(today):
    out = []
    for p in Person.query.filter(
            db.or_(Person.phone.is_(None), Person.phone == ""),
            db.or_(Person.email.is_(None), Person.email == "")):
        out.append(DerivedItem(
            source=f"contact:person:{p.id}", feed="contacts", kind="task",
            title=f"Add a phone or email for {p.name}", date=None, phase="planning",
            description="There is no way to reach them from this binder.",
            link=url_for("manage.edit_person", id=p.id), person_id=p.id))
    return out


# --- who inherits ----------------------------------------------------------

def _share_items(today):
    out = []
    for h in Holding.query.filter(Holding.side.in_(("asset", "equity"))):
        holder = h.entity.kind if h.entity_id else None
        if holder not in _NEEDS_BENEFICIARY:
            continue
        totals = h.share_totals()
        if not totals:
            title, sig = f"Name a beneficiary for {h.name}", "none"
            desc = "Nobody is named to receive it."
        else:
            off = {k: v for k, v in totals.items() if abs(v - 100) > 0.001}
            if not off:
                continue
            sig = ",".join(f"{k}={v:g}" for k, v in sorted(off.items()))
            title = f"Shares on {h.name} add up to {' / '.join(f'{v:g}%' for v in off.values())}"
            desc = "Each kind of designation should total 100%."
        out.append(DerivedItem(
            source=f"shares:holding:{h.id}@{sig}", feed="shares", kind="task",
            title=title, date=None, phase="planning", description=desc,
            link=_holding_link(h, "beneficiaries"), holding_id=h.id))
    return out


FEEDS = [
    Feed("bills", "bill", "Bills due", _bill_items, _bill_done,
         "Each recurring bill's next due date. Done moves it on by its frequency."),
    Feed("reviews", "review", "Trust reviews", _review_items, _review_done,
         "The trust's next review. Done schedules the following one."),
    Feed("verify", "verify", "Not verified lately", _verify_items, _verify_done,
         "Holdings nobody has marked verified within their type's window (default a year)."),
    Feed("values", "value", "Stale values", _value_items, None,
         "Holdings whose newest valuation is older than their type's window."),
    Feed("contacts", "contact", "Unreachable contacts", _contact_items, None,
         "People with neither a phone number nor an email."),
    Feed("shares", "shares", "Beneficiary gaps", _share_items, None,
         "Assets and stakes with nobody named, or shares that do not total 100%."),
]
_BY_PREFIX = {f.prefix: f for f in FEEDS}
assert len(_BY_PREFIX) == len(FEEDS), "two feeds share a source prefix"


def feed_for(source):
    if not source:
        return None
    return _BY_PREFIX.get(source.split(":", 1)[0])


def derived_items(today=None):
    """Every derived item that has not been touched yet."""
    today = today or date.today()
    touched = {s for (s,) in db.session.query(Event.source).filter(Event.source.isnot(None))}
    out = []
    for feed in FEEDS:
        out.extend(i for i in feed.items(today) if i.source not in touched)
    return out


def find(source, today=None):
    """The current derived item with this key, or None if it no longer applies."""
    feed = feed_for(source)
    if feed is None:
        return None
    return next((i for i in feed.items(today or date.today()) if i.source == source), None)
