"""What can happen to an event, and the one shape the pages show.

Stored events and derived items (src/services/feeds.py) look the same on
screen: a `Row`. Every action takes a row key - `event:<id>` for a stored
event, the source for a derived one - so the Now page's buttons do not need
to know which they are pressing.

Touching a derived item materialises it first: one Event is written with the
item's source, and the feed skips that source from then on.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from flask import url_for

from src.extensions import db
from src.models import (Event, EVENT_KIND_ICONS, EVENT_KIND_LABELS, EVENT_PHASE_LABELS)
from src.services import feeds
from src.services.dates import add_interval
from src.services.estate import get_root_entity

SNOOZE_DAYS = 7


@dataclass
class Row:
    key: str
    title: str
    kind: str
    phase: str
    date: Optional[date]
    done_at: Optional[date] = None
    description: str = ""
    link: str = "#"              # the record it is about
    edit_link: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: str = ""
    entity_id: Optional[int] = None   # the effective entity, root when none
    holding_id: Optional[int] = None
    derived: bool = False
    feed: str = ""
    repeats: bool = False
    # History rows (valuations, purchases) are not events; they name themselves.
    label: str = ""
    glyph: str = ""

    @property
    def kind_label(self):
        return self.label or EVENT_KIND_LABELS.get(self.kind, self.kind)

    @property
    def icon(self):
        return self.glyph or EVENT_KIND_ICONS.get(self.kind, "•")

    @property
    def phase_label(self):
        return EVENT_PHASE_LABELS.get(self.phase, self.phase)

    @property
    def is_done(self):
        return self.done_at is not None


def _record_link(event):
    if event.holding_id:
        return url_for("main.holding_details", id=event.holding_id)
    if event.person_id:
        return url_for("manage.edit_person", id=event.person_id)
    if event.entity_id:
        return url_for("main.details_view")
    return url_for("manage.edit_event", id=event.id)


def row_for_event(e, root_id):
    entity_id = e.entity_id or (e.holding.entity_id if e.holding else None) or root_id
    return Row(key=f"event:{e.id}", title=e.title, kind=e.kind, phase=e.phase,
               date=e.date, done_at=e.done_at, description=e.description or "",
               link=_record_link(e), edit_link=url_for("manage.edit_event", id=e.id),
               assignee_id=e.assignee_id,
               assignee_name=e.assignee.name if e.assignee else "",
               entity_id=entity_id, holding_id=e.holding_id, repeats=e.repeats)


def row_for_item(i, root_id):
    entity_id = i.entity_id
    if entity_id is None and i.holding_id:
        from src.models import Holding
        h = db.session.get(Holding, i.holding_id)
        entity_id = h.entity_id if h else None
    return Row(key=i.source, title=i.title, kind=i.kind, phase=i.phase, date=i.date,
               description=i.description, link=i.link, entity_id=entity_id or root_id,
               holding_id=i.holding_id, derived=True, feed=i.feed)


def all_rows(today=None, include_done=True):
    """Every stored event and every untouched derived item, as rows."""
    today = today or date.today()
    root_id = get_root_entity().id
    q = Event.query
    if not include_done:
        q = q.filter(Event.done_at.is_(None))
    rows = [row_for_event(e, root_id) for e in q.all()]
    rows += [row_for_item(i, root_id) for i in feeds.derived_items(today)]
    return rows


def apply_filters(rows, kinds=None, phases=None, assignee=None, entity=None):
    """kinds/phases: lists of codes; assignee: a person id, or "none"; entity:
    an entity id (the root trust's id matches everything held in the trust)."""
    out = []
    for r in rows:
        if kinds and r.kind not in kinds:
            continue
        if phases and r.phase not in phases:
            continue
        if assignee == "none" and r.assignee_id is not None:
            continue
        if assignee not in (None, "", "none") and r.assignee_id != int(assignee):
            continue
        if entity and r.entity_id != int(entity):
            continue
        out.append(r)
    return out


def _sort_key(r):
    return (r.date or date.max, r.title.lower())


def now_sections(rows, today=None, recent_days=14, recent_limit=10):
    """The Now page: overdue, this week, the next 30 days, needs attention
    (derived flags and undated tasks), recently done."""
    today = today or date.today()
    week, month = today + timedelta(days=7), today + timedelta(days=30)
    open_rows = [r for r in rows if not r.is_done]
    sections = {
        "overdue": [r for r in open_rows if r.date and r.date < today],
        "week": [r for r in open_rows if r.date and today <= r.date <= week],
        "month": [r for r in open_rows if r.date and week < r.date <= month],
        "attention": [r for r in open_rows if r.date is None],
    }
    for key in sections:
        sections[key].sort(key=_sort_key)
    recent = [r for r in rows if r.is_done and r.done_at >= today - timedelta(days=recent_days)]
    recent.sort(key=lambda r: (r.done_at, r.title), reverse=True)
    sections["recent"] = recent[:recent_limit]
    return sections


def next_up(today=None):
    """The soonest open dated row (overdue counts), or None."""
    dated = [r for r in all_rows(today, include_done=False) if r.date]
    return min(dated, key=_sort_key) if dated else None


# --- actions -----------------------------------------------------------------

class NotFound(LookupError):
    pass


def materialise(key, today=None):
    """The stored Event behind a row key, writing it first if the key is a
    derived item nobody has touched yet."""
    today = today or date.today()
    if key.startswith("event:"):
        event = db.session.get(Event, int(key.split(":", 1)[1]))
        if event is None:
            raise NotFound(key)
        return event
    existing = Event.query.filter_by(source=key).first()
    if existing is not None:
        return existing
    item = feeds.find(key, today)
    if item is None:
        raise NotFound(key)
    event = Event(kind=item.kind, title=item.title, date=item.date or today,
                  phase=item.phase, description=item.description or None,
                  holding_id=item.holding_id, entity_id=item.entity_id,
                  person_id=item.person_id, source=item.source)
    db.session.add(event)
    db.session.flush()
    return event


def complete(key, today=None):
    """Mark done. A derived item moves its record on (a bill's next due date,
    a verified stamp); a repeating event spawns its next occurrence."""
    today = today or date.today()
    event = materialise(key, today)
    if event.done_at is not None:
        return event, None
    event.done_at = today
    feed = feeds.feed_for(event.source)
    if feed and feed.on_done:
        feed.on_done(event.source, today)
    spawned = None
    if event.repeats:
        base = event.date or today
        spawned = Event(kind=event.kind, title=event.title,
                        date=add_interval(base, event.repeat_every, event.repeat_unit),
                        assignee_id=event.assignee_id, phase=event.phase,
                        description=event.description, holding_id=event.holding_id,
                        entity_id=event.entity_id, person_id=event.person_id,
                        repeat_every=event.repeat_every, repeat_unit=event.repeat_unit)
        db.session.add(spawned)
    db.session.flush()
    return event, spawned


def snooze(key, days=SNOOZE_DAYS, today=None):
    """Push it a week from today. On a derived flag this is how you say
    'not now': it becomes a dated event and comes back on that date."""
    today = today or date.today()
    event = materialise(key, today)
    if event.done_at is None:
        event.date = today + timedelta(days=days)
    db.session.flush()
    return event


def reopen(key):
    event = materialise(key)
    event.done_at = None
    db.session.flush()
    return event
