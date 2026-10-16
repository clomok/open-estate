"""Running a playbook: one event per step, dated from a trigger date.

Each event's source is `playbook:<playbook id>@<trigger date>:step:<step id>`,
so running the same playbook on the same date twice adds nothing the second
time, and a step added to the playbook later can be filled in by running it
again.
"""

from datetime import timedelta

from src.extensions import db
from src.models import Event, EVENT_KINDS, Person, PersonRole
from src.services.estate import get_root_entity


def step_source(playbook, trigger_date, step):
    return f"playbook:{playbook.id}@{trigger_date.isoformat()}:step:{step.id}"


def _first_with_role(role):
    if not role:
        return None
    return (Person.query.join(PersonRole).filter(PersonRole.role == role)
            .order_by(Person.id).first())


def run(playbook, trigger_date, phase="transition"):
    """Instantiate the playbook on trigger_date. Returns (created, skipped)."""
    root = get_root_entity()
    existing = {s for (s,) in db.session.query(Event.source)
                .filter(Event.source.like(f"playbook:{playbook.id}@{trigger_date.isoformat()}:%"))}
    created, skipped = [], 0
    for step in playbook.steps:
        source = step_source(playbook, trigger_date, step)
        if source in existing:
            skipped += 1
            continue
        lines = [step.instructions or ""]
        if step.document_type:
            lines.append(f"Find first: {step.document_type}")
        assignee = _first_with_role(step.who_role)
        event = Event(kind=step.kind if step.kind in EVENT_KINDS else "task",
                      title=step.title, date=trigger_date + timedelta(days=step.offset_days),
                      phase=phase, description="\n\n".join(l for l in lines if l) or None,
                      assignee_id=assignee.id if assignee else None,
                      entity_id=root.id, source=source)
        db.session.add(event)
        created.append(event)
    db.session.flush()
    return created, skipped


def runs(playbook):
    """Trigger dates this playbook has been run on, newest first, with the
    count of events each made."""
    counts = {}
    for (source,) in db.session.query(Event.source).filter(
            Event.source.like(f"playbook:{playbook.id}@%")):
        when = source.split("@", 1)[1].split(":", 1)[0]
        counts[when] = counts.get(when, 0) + 1
    return sorted(counts.items(), reverse=True)


def death_playbook():
    from src.models import Playbook
    return Playbook.query.filter_by(trigger="death_of_trustor").order_by(Playbook.id).first()
