"""The printed binder: the ledger arranged as the articles of a trust document.

Pure functions over model objects (anything with the same attributes will do,
which is how the unit tests drive them). The route gathers rows and calls
these; the template only lays out what comes back. Nothing here writes.
"""

from collections import OrderedDict
from datetime import date, timedelta

from src.holding_types import SIDES, mask, display_value
from src.models import FAMILY_ROLES, PERSON_ROLES
from src.services.feeds import needs_beneficiary


def ledger_totals(holdings):
    totals = {side: sum(h.value_cents for h in holdings if h.side == side) for side in SIDES}
    totals["net"] = totals["asset"] - totals["liability"]
    return totals


def balance_sheet(holdings):
    """{"by_side": {side: [(type_label, [holdings], subtotal_cents)]}, "totals": {...}}.

    Types run largest subtotal first; holdings inside a type likewise."""
    by_side = {}
    for side in SIDES:
        groups = OrderedDict()
        for h in holdings:
            if h.side == side:
                groups.setdefault(h.type_label, []).append(h)
        rows = [(label, sorted(hs, key=lambda h: (-h.value_cents, h.name.lower())),
                 sum(h.value_cents for h in hs)) for label, hs in groups.items()]
        rows.sort(key=lambda r: (-r[2], r[0].lower()))
        by_side[side] = rows
    return {"by_side": by_side, "totals": ledger_totals(holdings)}


def entity_sheets(entities, holdings):
    """One mini balance sheet per entity: the root first, add-ons by name.

    A holding with no entity belongs to the root (it sits in the trust)."""
    ordered = sorted(entities, key=lambda e: (not e.is_root, e.name.lower()))
    root = next((e for e in ordered if e.is_root), None)
    sheets = []
    for e in ordered:
        mine = [h for h in holdings
                if h.entity_id == e.id or (h.entity_id is None and e is root)]
        by = {side: sorted((h for h in mine if h.side == side),
                           key=lambda h: (-h.value_cents, h.name.lower())) for side in SIDES}
        totals = ledger_totals(mine)
        sheets.append({"entity": e, "assets": by["asset"], "liabilities": by["liability"],
                       "equity": by["equity"], "net_cents": totals["net"],
                       "totals": totals})
    return sheets


def who_gets_what(holdings, people):
    """The who-gets-what matrix: holdings that need an heir, by who is named.

    Scope is the Now page's beneficiary-gap rule (`feeds.needs_beneficiary`).
    `total_pct` is 100 for a complete row, otherwise the first kind of
    designation whose shares do not reach 100."""
    in_scope = [h for h in holdings if needs_beneficiary(h)]
    named = {d.person_id for h in in_scope for d in h.beneficiary_designations}
    beneficiaries = sorted((p for p in people if p.id in named), key=lambda p: p.name.lower())
    rows, undesignated = [], []
    for h in in_scope:
        if not h.beneficiary_designations:
            undesignated.append(h)
            continue
        cells = {}
        for d in h.beneficiary_designations:
            pct, kinds = cells.get(d.person_id, (0, []))
            cells[d.person_id] = (round(pct + d.percentage, 4),
                                  kinds + [d.kind_label])
        cells = {pid: (pct, " + ".join(kinds)) for pid, (pct, kinds) in cells.items()}
        off = [v for v in h.share_totals().values() if abs(v - 100) > 0.001]
        rows.append({"holding": h, "cells": cells,
                     "total_pct": off[0] if off else 100.0, "complete": not off})
    rows.sort(key=lambda r: (-r["holding"].value_cents, r["holding"].name.lower()))
    undesignated.sort(key=lambda h: (-h.value_cents, h.name.lower()))
    return {"beneficiaries": beneficiaries, "rows": rows, "undesignated": undesignated}


def people_by_role(people):
    """{role code: [person]} for roles somebody holds. Family roles first, then
    the professional team in the contacts page's order; within a role, in the
    order the roles were recorded (person_role has no position column)."""
    held = {}
    for p in people:
        for r in p.roles:
            held.setdefault(r.role, []).append((r.id, p))
    codes = [c for c, _ in PERSON_ROLES]
    codes = ([c for c in codes if c in FAMILY_ROLES] + [c for c in codes if c not in FAMILY_ROLES]
             + sorted(c for c in held if c not in codes))
    out = OrderedDict()
    for code in codes:
        if code in held:
            seen, ordered = set(), []
            for _, p in sorted(held[code], key=lambda t: t[0]):
                if p.id not in seen:
                    seen.add(p.id)
                    ordered.append(p)
            out[code] = ordered
    return out


def holding_facts(holding, reveal=False):
    """[(label, text)] for the facts recorded on a holding, sensitive ones
    masked unless `reveal`. Custom types list the fields their owner named."""
    attrs = holding.attributes or {}
    htype = holding.htype
    facts = []
    if htype and htype.custom:
        for row in attrs.get("fields", []):
            if row.get("value") not in (None, ""):
                facts.append((row.get("name", ""), str(row["value"])))
    elif htype:
        for f in htype.fields:
            if attrs.get(f.name) in (None, ""):
                continue
            text = display_value(f, attrs[f.name])
            facts.append((f.label, mask(attrs[f.name]) if f.is_sensitive and not reveal else text))
    return facts


def recent_valuations(holding, n=5):
    return sorted(holding.valuations, key=lambda v: (v.date, v.id or 0), reverse=True)[:n]


def record_counts(models):
    """{label: row count} for the backup's (label, Model) pairs."""
    return OrderedDict((label, model.query.count()) for label, model in models)


def colophon(holdings, counts, today):
    cutoff = today - timedelta(days=365)
    verified = sum(1 for h in holdings if h.last_verified and h.last_verified >= cutoff)
    return {"counts": counts, "holdings": len(holdings), "verified_last_year": verified,
            "generated": today}


def long_date(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}" if isinstance(d, date) else ""


def css_string(text):
    """Make text safe inside a double-quoted CSS string (a margin-box footer)."""
    out = str(text).replace("\\", "\\\\").replace('"', '\\"').replace("<", "\\3C ")
    return " ".join(out.split())
