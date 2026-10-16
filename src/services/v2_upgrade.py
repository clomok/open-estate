"""Convert a v1/v2 estate (the `asset` schema) into the v3 ledger shape.

ONE transform, two callers: the importer runs it on an old backup file, and
the v3 Alembic migration runs it on the rows of an old database. Both speak
the backup's JSON format, so both get exactly the same answer.

Frozen: v2 will never change, so this file should not either. If v4 arrives,
write v3 -> v4 as its own step rather than editing this one.

What it decides, so nobody has to rediscover it:
- A negative `value_estimated`, or type `Liability`, becomes side=liability
  with a positive value. Every other asset stays side=asset.
- `is_in_trust` True -> entity_id NULL (the trust). False -> an add-on entity
  of kind `individual`: one per owner, or one "Held outside the trust" when
  there was no owner.
- The one `trust_profile` row becomes the root entity (id 1). A database with
  none gets a default root, because v3 always has one.
- `person.role` becomes a single `person_role` row.
- Attribute keys the new type knows are parsed into their stored form (money
  -> cents, "3.5%" -> 3.5). Anything else - unknown keys, values that will not
  parse - is appended to the holding's notes. Nothing is dropped silently,
  with one exception: a liability's `outstanding_balance`, which is the value.
"""

from datetime import datetime, date

from src.holding_types import get_type, parse_field
from src.money import to_cents

ROOT_ENTITY_ID = 1

_ASSET_TYPE_MAP = {
    "realestate": "real_estate", "property": "real_estate",
    "vehicle": "vehicle",
    "bank": "bank", "financial": "bank",
    "investment": "investment",
    "jewelry": "jewelry", "art": "art",
    "personal": "other", "other": "other",
}
_RENAMES = {
    ("liability", "loan"): {"due_date": "payment_due_day", "lender": "lender"},
}
_DROP = {
    ("liability", "loan"): {"outstanding_balance", "current_value"},
}


def _key(code):
    return (code or "").replace("_", "").replace(" ", "").lower()


def _side_and_type(asset):
    code = _key(asset.get("asset_type"))
    value = asset.get("value_estimated") or 0
    if code == "liability":
        return "liability", "loan"
    if value < 0:
        return "liability", "other"
    return "asset", _ASSET_TYPE_MAP.get(code, "other")


def _date(value):
    if value in (None, ""):
        return None
    if isinstance(value, (datetime, date)):
        return (value.date() if isinstance(value, datetime) else value).isoformat()
    text = str(value)
    try:
        return datetime.fromisoformat(text).date().isoformat()
    except ValueError:
        return date.fromisoformat(text[:10]).isoformat()


def _cents(value):
    return abs(to_cents(value) or 0)


def _attributes(side, code, raw):
    """-> (attributes, leftover note lines)."""
    htype = get_type(side, code)
    renames = _RENAMES.get((side, code), {})
    drop = _DROP.get((side, code), set())
    attrs, leftovers = {}, []
    for key, value in (raw or {}).items():
        if value in (None, "") or key in drop:
            continue
        if key == "notes":
            leftovers.append(str(value))
            continue
        name = renames.get(key, key)
        field = htype.field(name) if htype else None
        if field is None:
            leftovers.append(f"{key.replace('_', ' ').capitalize()}: {value}")
            continue
        try:
            parsed = parse_field(field, value)
        except ValueError:
            leftovers.append(f"{field.label}: {value}")
            continue
        if parsed is not None:
            attrs[name] = parsed
    return attrs, leftovers


def convert(data, now=None):
    """v1/v2 backup dict -> v3 backup dict (JSON-safe, same layout as export)."""
    stamp = (now or datetime.now()).replace(microsecond=0).isoformat()
    audit = {"created_at": stamp, "updated_at": stamp, "last_verified": None}

    def rows(key):
        return list(data.get(key) or [])

    people = rows("people")
    person_names = {p["id"]: p.get("name") or f"Person {p['id']}" for p in people}

    out = {"version": "3.0", "timestamp": data.get("timestamp") or stamp,
           "upgraded_from": str(data.get("version") or "unknown")}

    out["people"] = [
        {"id": p["id"], "name": p.get("name") or "(no name)", "kind": "individual",
         "email": p.get("email"), "phone": p.get("phone"),
         "attributes": p.get("attributes") or {}, **audit}
        for p in people
    ]
    out["person_roles"] = [
        {"id": i, "person_id": p["id"], "role": p["role"], **audit}
        for i, p in enumerate((p for p in people if p.get("role")), start=1)
    ]

    # Root entity from the old singleton.
    profile = (rows("trust_profile") or [{}])[0]
    entities = [{
        "id": ROOT_ENTITY_ID, "kind": "trust",
        "name": profile.get("name") or "The Family Trust",
        "is_root": True, "parent_id": None, "person_id": None,
        "date_established": _date(profile.get("date_established")),
        "date_death_estimated": _date(profile.get("date_death_estimated")),
        "date_death_actual": _date(profile.get("date_death_actual")),
        "review_frequency": profile.get("review_frequency") or "Annual",
        "next_review_date": _date(profile.get("next_review_date")),
        "notes": profile.get("notes"), "attributes": {}, **audit,
    }]
    personal_entity = {}     # owner_id (or None) -> entity id

    def entity_for_outside(owner_id):
        if owner_id not in personal_entity:
            new_id = len(entities) + 1
            name = (f"{person_names[owner_id]} (personally held)"
                    if owner_id in person_names else "Held outside the trust")
            entities.append({
                "id": new_id, "kind": "individual", "name": name, "is_root": False,
                "parent_id": ROOT_ENTITY_ID,
                "person_id": owner_id if owner_id in person_names else None,
                "date_established": None, "date_death_estimated": None,
                "date_death_actual": None, "review_frequency": None,
                "next_review_date": None,
                "notes": "Created when the ledger moved to v3, for holdings "
                         "that were marked as not held in the trust.",
                "attributes": {}, **audit,
            })
            personal_entity[owner_id] = new_id
        return personal_entity[owner_id]

    holdings, in_trust = [], {}
    for a in rows("assets"):
        side, code = _side_and_type(a)
        attrs, leftovers = _attributes(side, code, a.get("attributes"))
        original = a.get("asset_type")
        if code == "other" and _key(original) not in ("other", "personal", ""):
            leftovers.insert(0, f"Type before v3: {original}")
        owner_id = a.get("owner_id")
        trust = a.get("is_in_trust") not in (False, 0)     # None was the old default: True
        holdings.append({
            "id": a["id"], "side": side, "type_code": code,
            "name": a.get("name") or "(no name)",
            "entity_id": None if trust else entity_for_outside(owner_id),
            "owner_id": owner_id, "value_cents": _cents(a.get("value_estimated")),
            "attributes": attrs, "ownership_pct": None, "secured_by_id": None,
            "notes": "\n".join(leftovers) or None, **audit,
        })
        in_trust[a["id"]] = trust
    out["entities"] = entities
    out["holdings"] = holdings

    out["valuations"] = [
        {"id": r["id"], "holding_id": r["asset_id"], "date": _date(r.get("date")),
         "value_cents": _cents(r.get("value")), "source": r.get("source"),
         "notes": r.get("notes"), **audit}
        for r in rows("appraisals")
    ]
    out["beneficiary_designations"] = [
        {"id": i, "holding_id": r["asset_id"], "person_id": r["person_id"],
         "percentage": r.get("percentage") if r.get("percentage") is not None else 50.0,
         "kind": "trust_schedule" if in_trust.get(r["asset_id"], True) else "will",
         "notes": None, **audit}
        for i, r in enumerate(rows("asset_beneficiaries"), start=1)
    ]
    out["tasks"] = [
        {"id": r["id"], "title": r.get("title"), "status": r.get("status"),
         "due_date": _date(r.get("due_date")), "is_recurring": bool(r.get("is_recurring")),
         "holding_id": r.get("asset_id"), **audit}
        for r in rows("tasks")
    ]
    out["milestones"] = [
        {"id": r["id"], "title": r.get("title"), "date_event": _date(r.get("date_event")),
         "description": r.get("description"), "is_completed": bool(r.get("is_completed")),
         **audit}
        for r in rows("milestones")
    ]

    def sub(key, extra=None):
        result = []
        for r in rows(key):
            row = {k: v for k, v in r.items() if k != "asset_id"}
            row["holding_id"] = r["asset_id"]
            if extra:
                row = extra(row)
            row.update(audit)
            result.append(row)
        return result

    def bill(row):
        row["amount_cents"] = _cents(row.pop("amount_estimated", 0))
        row["is_autopay"] = bool(row.get("is_autopay"))
        return row

    out["structures"] = sub("structures")
    out["location_points"] = sub("location_points")
    out["bills"] = sub("bills", bill)
    out["vendors"] = sub("vendors")
    return out
