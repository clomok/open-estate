"""The history half of the timeline: what already happened to the estate
that is not an event - valuations, purchases, maintenance.

Done events come from src/services/events.py; this adds the rest in the same
Row shape, so the timeline page renders one list. Every row links back to
the holding it is about.
"""

from datetime import date

from flask import url_for

from src.models import Holding, PropertyStructure
from src.money import format_cents
from src.services.estate import get_root_entity
from src.services.events import Row

# (code, label) - the timeline's filter chips for things that are not events.
HISTORY_KINDS = [("valuation", "Valuations"), ("acquisition", "Purchases"),
                 ("maintenance", "Maintenance")]


def history_rows(kinds=None, entity=None):
    root_id = get_root_entity().id
    want = set(kinds or [k for k, _ in HISTORY_KINDS])
    out = []
    for h in Holding.query.all():
        eid = h.entity_id or root_id
        if entity and eid != int(entity):
            continue
        link = url_for("main.holding_details", id=h.id)
        purchase = (h.attributes or {}).get("purchase_date")
        if "acquisition" in want and purchase:
            try:
                when = date.fromisoformat(purchase)
            except ValueError:
                when = None
            if when:
                out.append(Row(key=f"acquired:{h.id}", title=h.name, kind="acquisition",
                               phase="now", date=when, done_at=when, link=link,
                               description="Acquired for the estate.", entity_id=eid,
                               holding_id=h.id, label="Purchased", glyph=h.icon))
        if "valuation" in want:
            for v in h.valuations:
                if v.source == "Purchase":
                    continue          # the acquisition row already says it
                out.append(Row(key=f"valuation:{v.id}", title=h.name, kind="valuation",
                               phase="now", date=v.date, done_at=v.date, link=link,
                               description=f"Valued at {format_cents(v.value_cents)}"
                                           + (f" ({v.source})" if v.source else ""),
                               entity_id=eid, holding_id=h.id, label="Valuation",
                               glyph=h.icon))
    if "maintenance" in want:
        for s in PropertyStructure.query.filter(PropertyStructure.date_last_maintained.isnot(None)):
            eid = s.holding.entity_id or root_id
            if entity and eid != int(entity):
                continue
            out.append(Row(key=f"maintained:{s.id}", title=s.name, kind="maintenance",
                           phase="now", date=s.date_last_maintained,
                           done_at=s.date_last_maintained,
                           link=url_for("main.holding_details", id=s.holding_id) + "#structures",
                           description=s.notes or "Maintenance logged.", entity_id=eid,
                           holding_id=s.holding_id, label="Maintenance", glyph="🛠️"))
    return out
