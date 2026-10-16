"""v3 -> v4: `task` and `milestone` become one `event` table.

One function, two callers, exactly as v2_upgrade: the migration that
introduces the event table feeds it the rows of the old tables, and the
importer feeds it a v3 backup file. Either way the result is the same.

Frozen once released. A v5 gets its own step.

What moves where:
- task      -> event kind "task"; status "Done" sets done_at (the day the
               row was last changed, the best date there is). `is_recurring`
               never said how often, so it is not turned into a repeat: the
               description says "(was marked recurring)" and the person sets
               the interval.
- milestone -> event kind "milestone"; is_completed sets done_at to the
               milestone's own date.
Tasks keep their ids; milestones are numbered after the last task, so the
order is stable and nothing collides.

A v3 backup has no playbooks. The default one is added, so a restored old
file comes back with the same starting playbook a fresh install has.
"""

from src.services import default_playbook


def _date_part(value):
    if value is None:
        return None
    return str(value)[:10]


def _audit(row):
    """Carry the audit columns that are there; leave absent ones to the
    column defaults (row_kwargs skips keys it is not given)."""
    return {k: row[k] for k in ("created_at", "updated_at", "last_verified")
            if row.get(k) is not None}


def events_from(tasks, milestones):
    events = []
    for t in sorted(tasks, key=lambda r: r["id"]):
        desc = None
        if t.get("is_recurring"):
            desc = "(was marked recurring)"
        status = (t.get("status") or "").strip().lower()
        events.append({
            "id": t["id"], "kind": "task", "title": t.get("title") or "Untitled task",
            "date": _date_part(t.get("due_date")),
            "done_at": (_date_part(t.get("updated_at")) or _date_part(t.get("due_date"))
                        if status in ("done", "complete", "completed") else None),
            "assignee_id": None, "phase": "now", "description": desc,
            "holding_id": t.get("holding_id"), "entity_id": None, "person_id": None,
            "source": None, "repeat_every": None, "repeat_unit": None,
            **_audit(t),
        })
    next_id = max((e["id"] for e in events), default=0) + 1
    for m in sorted(milestones, key=lambda r: r["id"]):
        when = _date_part(m.get("date_event"))
        events.append({
            "id": next_id, "kind": "milestone", "title": m.get("title") or "Untitled milestone",
            "date": when,
            "done_at": (when or _date_part(m.get("updated_at"))) if m.get("is_completed") else None,
            "assignee_id": None, "phase": "planning", "description": m.get("description"),
            "holding_id": None, "entity_id": None, "person_id": None,
            "source": None, "repeat_every": None, "repeat_unit": None,
            **_audit(m),
        })
        next_id += 1
    return events


def default_playbook_rows():
    playbook = {"id": 1, "name": default_playbook.NAME,
                "description": default_playbook.DESCRIPTION,
                "trigger": default_playbook.TRIGGER}
    steps = [dict(id=i, **row)
             for i, row in enumerate(default_playbook.step_rows(1), start=1)]
    return [playbook], steps


def convert(data):
    """A v3 backup dict -> v4. Leaves the input untouched."""
    out = {k: v for k, v in data.items() if k not in ("tasks", "milestones")}
    out["version"] = "4.0"
    out["events"] = events_from(data.get("tasks", []), data.get("milestones", []))
    if not data.get("playbooks"):
        out["playbooks"], out["playbook_steps"] = default_playbook_rows()
    return out
