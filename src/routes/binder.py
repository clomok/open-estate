"""The printed binder: one long readable document, printed with the browser."""

import os
from datetime import date

from flask import Blueprint, current_app, render_template, request, url_for

from src.models import PERSON_ROLES, Entity, Holding, LocationPoint, Person, RecurringBill
from src.routes.main import _by_month
from src.services import binder as svc, events as event_service, playbooks as playbook_service
from src.services.auth_service import login_required
from src.services.backup_schema import BACKUP_MODELS
from src.services.estate import get_root_entity

bp = Blueprint('binder', __name__)

# The three toggles, all off by default; each is switched on by `?name=1`.
BASE_OPTIONS = {"planning": False, "reveal": False, "hide_empty": False}


def read_options(args):
    return {k: args.get(k) == "1" for k in BASE_OPTIONS}


@bp.route('/binder/setup')
@login_required
def binder_setup():
    return render_template('binder_setup.html', root=get_root_entity(), active_page='details')


@bp.route('/binder')
@login_required
def binder_view():
    return render_binder(read_options(request.args))


def render_binder(options, offline=False):
    """The binder page as HTML. `offline` is the copy saved into a backup zip:
    one self-contained file, with no top bar and no link back into the app."""
    today = date.today()
    root = get_root_entity()
    entities = Entity.query.all()
    holdings = Holding.query.all()
    people = Person.query.order_by(Person.name).all()
    roles = svc.people_by_role(people)

    side_order = {"asset": 0, "liability": 1, "equity": 2}
    cards = [{"holding": h,
              "facts": svc.holding_facts(h, reveal=options["reveal"]),
              "valuations": svc.recent_valuations(h)}
             for h in sorted(holdings, key=lambda h: (side_order[h.side], h.type_label.lower(),
                                                      h.name.lower()))]
    bills = sorted(RecurringBill.query.all(),
                   key=lambda b: (b.next_due_date is None, b.next_due_date or date.max,
                                  b.name.lower()))
    matrix = svc.who_gets_what(holdings, people)
    pins = LocationPoint.query.order_by(LocationPoint.holding_id, LocationPoint.label).all()
    extra = {}
    if options["planning"]:
        pb = playbook_service.death_playbook()
        extra["playbook"] = pb
        extra["bands"] = svc.playbook_bands(pb.steps if pb else [], roles)
        rows = event_service.all_rows(today)
        extra["ahead_months"] = _by_month(svc.year_ahead(rows, today), lambda r: r.date)
        extra["attention"] = sorted(
            (r for r in event_service.now_sections(rows, today)["attention"]),
            key=lambda r: r.title.lower())
    hidden = {
        "art-ii": not any(roles.get(c) for c in ("Trustee", "SuccessorTrustee", "Executor")),
        "art-iii": not holdings,
        "sched-a": not cards,
        "art-iv": not matrix["rows"] and not matrix["undesignated"],
        "art-v": not (roles.get("Attorney") or roles.get("Medical")),
        "art-vii": True, "art-viii": True, "sched-c": True,     # Phase C stubs
        "art-ix": not pins,
        "art-x": not root.notes,
        "art-xi": not roles,
        "sched-b": not bills,
    }
    if options["planning"]:
        hidden["art-vi"] = not extra["bands"]
        hidden["appendix"] = not (extra["ahead_months"] or extra["attention"])
    hidden = {k for k, v in hidden.items() if v}
    toggle_links = None if offline else {k: url_for('binder.binder_view',
                               **{o: 1 for o, on in {**options, k: not options[k]}.items() if on})
                    for k in options}
    footer = f"{root.name} · estate binder · {svc.long_date(today)}"
    inline_css = None
    if offline:
        css_dir = os.path.join(current_app.static_folder, 'css')
        inline_css = "\n".join(open(os.path.join(css_dir, f), encoding='utf-8').read()
                               for f in ('style.css', 'binder.css'))
    return render_template(
        'binder.html',
        offline=offline, inline_css=inline_css,
        root=root, today=today, options=options, long_date=svc.long_date,
        footer=svc.css_string(footer),
        roles=roles, role_labels=PERSON_ROLES,
        trustors=roles.get("Trustor", []),
        sheet=svc.balance_sheet(holdings),
        entity_sheets=svc.entity_sheets(entities, holdings),
        matrix=matrix,
        cards=cards, bills=bills,
        pins=pins,
        toggle_links=toggle_links,
        hidden=hidden if options["hide_empty"] else set(),
        **extra,
        colophon=svc.colophon(holdings, svc.record_counts(BACKUP_MODELS), today))
