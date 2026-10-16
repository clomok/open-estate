from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for
from src.services.auth_service import login_required
from src.services.timeline_service import get_timeline_events
from src.services.estate import get_root_entity, addon_entities
from src.models import Person, Holding, FAMILY_ROLES, DESIGNATION_KIND_LABELS
from src.forms import ValuationForm, DesignationForm
from src.holding_types import SIDES, SIDE_META
from src.money import cents_to_dollars

bp = Blueprint('main', __name__)


def ledger_totals(holdings):
    totals = {side: sum(h.value_cents for h in holdings if h.side == side) for side in SIDES}
    totals["net"] = totals["asset"] - totals["liability"]
    return totals


@bp.route('/')
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
    # Get filters from URL
    active_filters = request.args.getlist('type')
    if not active_filters:
        active_filters = None

    all_events = get_timeline_events(active_filters)
    today = date.today()

    # History = everything up to today; upcoming = everything after.
    history = [e for e in all_events if e['date'] <= today]
    upcoming = [e for e in all_events if e['date'] > today]
    history.sort(key=lambda x: x['date'], reverse=True)
    upcoming.sort(key=lambda x: x['date'])

    return render_template('timeline.html',
                           history=history,
                           upcoming=upcoming,
                           active_page='timeline',
                           current_filters=active_filters or [])


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
