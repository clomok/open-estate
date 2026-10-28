"""The printed binder: one long readable document, printed with the browser."""

from datetime import date

from flask import Blueprint, render_template

from src.models import PERSON_ROLES, Entity, Holding, LocationPoint, Person, RecurringBill
from src.services import binder as svc
from src.services.auth_service import login_required
from src.services.backup_schema import BACKUP_MODELS
from src.services.estate import get_root_entity

bp = Blueprint('binder', __name__)

# What the toggles will switch (step 2). Base print: all off.
BASE_OPTIONS = {"planning": False, "reveal": False, "hide_empty": False}


@bp.route('/binder')
@login_required
def binder_view():
    today = date.today()
    options = dict(BASE_OPTIONS)
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
    footer = f"{root.name} · estate binder · {svc.long_date(today)}"
    return render_template(
        'binder.html',
        root=root, today=today, options=options, long_date=svc.long_date,
        footer=svc.css_string(footer),
        roles=roles, role_labels=PERSON_ROLES,
        trustors=roles.get("Trustor", []),
        sheet=svc.balance_sheet(holdings),
        entity_sheets=svc.entity_sheets(entities, holdings),
        matrix=svc.who_gets_what(holdings, people),
        cards=cards, bills=bills,
        pins=LocationPoint.query.order_by(LocationPoint.holding_id, LocationPoint.label).all(),
        colophon=svc.colophon(holdings, svc.record_counts(BACKUP_MODELS), today))
