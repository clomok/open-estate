from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for
from src.services.auth_service import login_required
from src.services.timeline_service import history_rows, HISTORY_KINDS
from src.services import events as event_service, playbooks as playbook_service
from src.services.default_playbook import DISCLAIMER
from src.services.estate import get_root_entity, addon_entities
from src.models import (Person, Holding, Playbook, FAMILY_ROLES, DESIGNATION_KIND_LABELS,
                        EVENT_KINDS, EVENT_KIND_LABELS, EVENT_PHASES, EVENT_PHASE_LABELS,
                        PERSON_ROLES)
from src.forms import ValuationForm, DesignationForm
from src.holding_types import SIDES, SIDE_META
from src.money import cents_to_dollars

bp = Blueprint('main', __name__)


def ledger_totals(holdings):
    totals = {side: sum(h.value_cents for h in holdings if h.side == side) for side in SIDES}
    totals["net"] = totals["asset"] - totals["liability"]
    return totals


def _filters():
    """The filter bar shared by the Now and Timeline pages, read from the URL."""
    return {
        "kinds": request.args.getlist("kind"),
        "phases": request.args.getlist("phase"),
        "assignee": request.args.get("assignee", ""),
        "entity": request.args.get("entity", type=int),
    }


def _filter_options():
    root = get_root_entity()
    return {
        "people": Person.query.order_by(Person.name).all(),
        "entities": [root] + addon_entities(),
        "phases": [(p, EVENT_PHASE_LABELS[p]) for p in EVENT_PHASES],
        "kinds": [(k, EVENT_KIND_LABELS[k]) for k in EVENT_KINDS],
    }


@bp.route('/')
@login_required
def now():
    """Home: what needs doing now."""
    today = date.today()
    f = _filters()
    rows = event_service.apply_filters(event_service.all_rows(today), f["kinds"],
                                       f["phases"], f["assignee"], f["entity"])
    sections = event_service.now_sections(rows, today)
    root = get_root_entity()
    pb = playbook_service.death_playbook()
    return render_template('now.html', sections=sections, today=today, filters=f,
                           options=_filter_options(), root=root,
                           death_playbook=pb,
                           death_playbook_runs=playbook_service.runs(pb) if pb else [],
                           active_page='now')


@bp.route('/overview')
@login_required
def dashboard():
    root = get_root_entity()
    holdings = Holding.query.all()
    totals = ledger_totals(holdings)
    trust_count = sum(1 for h in holdings if h.in_trust)

    # --- CHART DATA PREPARATION ---
    # Net worth is assets minus liabilities, so only those two sides are
    # charted; equity stakes are shown beside it (see Holding.signed_cents).
    charted = [h for h in holdings if h.side in ("asset", "liability")]
    all_dates = {v.date for h in charted for v in h.valuations}
    all_dates.add(date.today())
    sorted_dates = sorted(all_dates)

    asset_colors = ['#16a34a', '#2563eb', '#9333ea', '#0891b2', '#0d9488',
                    '#4f46e5', '#059669', '#7c3aed', '#0284c7', '#65a30d']
    liability_colors = ['#dc2626', '#ea580c', '#db2777', '#b91c1c', '#c2410c',
                        '#be123c', '#991b1b', '#9a3412', '#831843', '#7f1d1d']
    a_idx = l_idx = 0
    datasets = []
    for h in charted:
        sign = 1 if h.side == "asset" else -1
        vals = sorted(h.valuations, key=lambda v: v.date)
        by_date = {v.date: v.value_cents for v in vals}
        start = vals[0].date if vals else date.max
        points, current = [], 0
        for d in sorted_dates:
            if d in by_date:
                current = by_date[d]
            elif d < start:
                current = 0
            points.append(sign * cents_to_dollars(current))
        if h.side == "liability":
            color = liability_colors[l_idx % len(liability_colors)]; l_idx += 1
        else:
            color = asset_colors[a_idx % len(asset_colors)]; a_idx += 1
        datasets.append({'id': h.id, 'label': h.name, 'data': points, 'color': color,
                         'type': h.type_code, 'side': h.side})

    chart_payload = {'dates': [d.isoformat() for d in sorted_dates], 'datasets': datasets}

    return render_template('dashboard.html',
                           active_page='overview',
                           root=root,
                           totals=totals,
                           trust_count=trust_count,
                           next_event=event_service.next_up(),
                           today=date.today(),
                           chart_payload=chart_payload)


@bp.route('/assets')
@login_required
def assets_view():
    """Old address of the ledger page."""
    return redirect(url_for('main.holdings_view'))


@bp.route('/holdings')
@login_required
def holdings_view():
    holdings = Holding.query.all()
    by_side = {side: sorted([h for h in holdings if h.side == side],
                            key=lambda h: h.value_cents, reverse=True)
               for side in SIDES}
    return render_template('holdings.html',
                           by_side=by_side,
                           side_meta=SIDE_META,
                           totals=ledger_totals(holdings),
                           root=get_root_entity(),
                           active_page='assets')


@bp.route('/asset/<int:id>')
@login_required
def asset_details(id):
    return redirect(url_for('main.holding_details', id=id))


@bp.route('/holding/<int:id>')
@login_required
def holding_details(id):
    holding = Holding.query.get_or_404(id)
    form = ValuationForm()

    history = sorted(holding.valuations, key=lambda v: v.date)
    if history:
        dates = [v.date.isoformat() for v in history]
        values = [cents_to_dollars(v.value_cents) for v in history]
    else:
        dates = [date.today().isoformat()]
        values = [cents_to_dollars(holding.value_cents)]

    designation_form = DesignationForm()
    people = Person.query.order_by(Person.name).all()
    designation_form.person_id.choices = [(p.id, p.name) for p in people]

    return render_template('holding_details.html',
                           holding=holding,
                           htype=holding.htype,
                           root=get_root_entity(),
                           form=form,
                           designation_form=designation_form,
                           people=people,
                           kind_labels=DESIGNATION_KIND_LABELS,
                           chart_dates=dates,
                           chart_values=values,
                           active_page='assets')


@bp.route('/timeline')
@login_required
def timeline_view():
    """Upcoming (every open event and derived item, overdue first) beside
    history (done events, valuations, acquisitions, maintenance)."""
    today = date.today()
    f = _filters()
    event_kinds = [k for k in f["kinds"] if k in EVENT_KINDS]
    history_kinds = [k for k in f["kinds"] if k in dict(HISTORY_KINDS)]

    rows = event_service.all_rows(today)
    upcoming, history = [], []
    if not f["kinds"] or event_kinds:
        rows = event_service.apply_filters(rows, event_kinds, f["phases"],
                                           f["assignee"], f["entity"])
        upcoming = [r for r in rows if not r.is_done and r.date]
        undated = [r for r in rows if not r.is_done and not r.date]
        history = [r for r in rows if r.is_done]
    else:
        undated = []
    # Valuations, purchases and maintenance have no phase or assignee: they
    # drop out when either of those filters is set.
    if (not f["kinds"] or history_kinds) and not f["phases"] and not f["assignee"]:
        history += history_rows(history_kinds or None, f["entity"])

    upcoming.sort(key=lambda r: (r.date, r.title.lower()))
    history.sort(key=lambda r: (r.done_at or r.date), reverse=True)

    return render_template('timeline.html',
                           history=history,
                           upcoming=upcoming,
                           undated=undated,
                           today=today,
                           filters=f,
                           options=_filter_options(),
                           history_kinds=HISTORY_KINDS,
                           active_page='timeline')


@bp.route('/playbooks')
@login_required
def playbooks_view():
    pbs = Playbook.query.order_by(Playbook.name).all()
    return render_template('playbooks.html', playbooks=pbs,
                           runs={pb.id: playbook_service.runs(pb) for pb in pbs},
                           disclaimer=DISCLAIMER, active_page='playbooks')


@bp.route('/playbook/<int:id>')
@login_required
def playbook_view(id):
    pb = Playbook.query.get_or_404(id)
    return render_template('playbook.html', playbook=pb, runs=playbook_service.runs(pb),
                           role_labels=dict(PERSON_ROLES), disclaimer=DISCLAIMER,
                           active_page='playbooks')


@bp.route('/contacts')
@login_required
def contacts_view():
    all_people = Person.query.order_by(Person.name).all()

    family = [p for p in all_people if p.has_role(*FAMILY_ROLES)]
    pros = [p for p in all_people if not p.has_role(*FAMILY_ROLES)]

    pro_roles_meta = [
        ('Attorney', 'Estate Attorney'),
        ('Financial Advisor', 'Financial Advisor'),
        ('Accountant', 'CPA / Accountant'),
        ('Funeral Director', 'Funeral Service'),
        ('Insurance', 'Insurance Agent'),
        ('Medical', 'Primary Doctor'),
    ]
    existing_roles = {r for p in all_people for r in p.role_codes}
    missing_pros = [{'role': code, 'label': label}
                    for code, label in pro_roles_meta if code not in existing_roles]

    return render_template('contacts.html',
                           family=family,
                           pros=pros,
                           missing_pros=missing_pros,
                           active_page='contacts')


@bp.route('/details')
@login_required
def details_view():
    """The trust - the root entity - and the add-ons attached to it."""
    root = get_root_entity()
    addons = addon_entities()
    trust_holdings = Holding.query.filter(Holding.entity_id.is_(None)).all()
    return render_template('details.html',
                           profile=root,
                           addons=addons,
                           trust_totals=ledger_totals(trust_holdings),
                           addon_totals={e.id: ledger_totals(e.holdings) for e in addons},
                           active_page='details')


@bp.route('/faq')
@login_required
def faq_view():
    return render_template('faq.html', active_page='faq')
