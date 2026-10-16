from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from sqlalchemy.exc import IntegrityError

from src.extensions import db
from src.models import (Holding, Person, Valuation, PropertyStructure, LocationPoint,
                        RecurringBill, HoldingVendor, BeneficiaryDesignation, Entity,
                        Event, Playbook, PlaybookStep)
from src.forms import (build_holding_form, ValuationForm, PersonForm, DesignationForm,
                       StructureForm, LocationPointForm, RecurringBillForm,
                       HoldingVendorForm, TrustProfileForm, EntityForm,
                       EventForm, PlaybookForm, PlaybookStepForm, RunPlaybookForm)
from src.services import events as event_service, playbooks as playbook_service
from src.services import default_playbook
from src.holding_types import (SIDES, SIDE_META, get_type, types_for, parse_field,
                               validate_attributes, input_value)
from src.services.auth_service import login_required
from src.services.estate import get_root_entity, addon_entities

bp = Blueprint('manage', __name__, url_prefix='/manage')


# --- HOLDINGS ----------------------------------------------------------------

@bp.route('/holding/select-type')
@bp.route('/asset/select-type')
@login_required
def select_type():
    sides = [(side, SIDE_META[side], types_for(side)) for side in SIDES]
    return render_template('select_type.html', sides=sides, active_page='assets')


def _form_choices(form, holding=None):
    root = get_root_entity()
    form.entity_id.choices = [(0, f"{root.name} (the trust)")] + [
        (e.id, f"{e.name} · {e.kind_label}") for e in addon_entities()]
    people = Person.query.order_by(Person.name).all()
    form.owner_id.choices = [(0, '— No individual owner —')] + [(p.id, p.name) for p in people]
    assets = Holding.query.filter_by(side="asset").order_by(Holding.name).all()
    form.secured_by_id.choices = [(0, '— Not secured —')] + [
        (h.id, h.name) for h in assets if holding is None or h.id != holding.id]


def _prefill(form, holding, htype):
    """GET of the edit page: put the stored values into the form."""
    form.name.data = holding.name
    form.value.data = holding.value_cents
    form.entity_id.data = holding.entity_id or 0
    form.owner_id.data = holding.owner_id or 0
    form.ownership_pct.data = holding.ownership_pct
    form.secured_by_id.data = holding.secured_by_id or 0
    form.notes.data = holding.notes
    attrs = holding.attributes or {}
    if htype.custom:
        form.custom_type_label.data = attrs.get("type_label", "")
    for f in htype.fields:
        if f.name in attrs:
            getattr(form, "attr_" + f.name).data = input_value(f, attrs[f.name])


def _custom_rows():
    names = request.form.getlist("custom_name")
    values = request.form.getlist("custom_value")
    return [{"name": n.strip(), "value": v.strip()}
            for n, v in zip(names, values) if n.strip()]


def _save_holding(holding, form, htype, leftover_notes=()):
    """Copy a validated form onto a holding. Returns a list of problems; the
    holding is only changed when the list is empty."""
    if htype.custom:
        attrs = {"type_label": form.custom_type_label.data.strip(), "fields": _custom_rows()}
    else:
        attrs = {}
        for f in htype.fields:
            value = parse_field(f, getattr(form, "attr_" + f.name).data)
            if value is not None:
                attrs[f.name] = value
    problems = validate_attributes(htype, attrs)

    secured_by = form.secured_by_id.data or None
    if htype.side == "liability" and secured_by:
        target = db.session.get(Holding, secured_by)
        if target is None or target.side != "asset" or target.id == holding.id:
            problems.append("A liability can only be secured by an asset.")
    if problems:
        return problems

    root = get_root_entity()
    holding.side = htype.side
    holding.type_code = htype.code
    holding.name = form.name.data
    holding.value_cents = form.value.data or 0
    entity_id = form.entity_id.data or None
    holding.entity_id = None if entity_id == root.id else entity_id
    holding.owner_id = form.owner_id.data or None
    holding.ownership_pct = form.ownership_pct.data if htype.side == "equity" else None
    holding.secured_by_id = secured_by if htype.side == "liability" else None
    notes = (form.notes.data or "").strip()
    if leftover_notes:
        notes = "\n".join([notes, *leftover_notes]).strip()
    holding.notes = notes or None
    holding.attributes = attrs
    return []


def _sync_value(holding):
    """The holding's value is its most recent valuation, when it has any."""
    latest = (Valuation.query.filter_by(holding_id=holding.id)
              .order_by(Valuation.date.desc(), Valuation.id.desc()).first())
    if latest:
        holding.value_cents = latest.value_cents


@bp.route('/holding/new/<side>/<type_code>', methods=['GET', 'POST'])
@login_required
def create_holding(side, type_code):
    htype = get_type(side, type_code)
    if htype is None:
        abort(404)
    form = build_holding_form(htype)()
    _form_choices(form)
    if request.method == 'GET':
        form.entity_id.data = 0

    if form.validate_on_submit():
        holding = Holding()
        problems = _save_holding(holding, form, htype)
        if not problems:
            db.session.add(holding)
            db.session.flush()

            # Opening history: the purchase, then today's value.
            attrs = holding.attributes or {}
            purchase_date = attrs.get("purchase_date")
            if purchase_date:
                db.session.add(Valuation(holding_id=holding.id,
                                         date=date.fromisoformat(purchase_date),
                                         value_cents=attrs.get("purchase_price") or 0,
                                         source="Purchase", notes="Original purchase price"))
            if holding.value_cents and not (
                    purchase_date == date.today().isoformat()
                    and attrs.get("purchase_price") == holding.value_cents):
                db.session.add(Valuation(holding_id=holding.id, date=date.today(),
                                         value_cents=holding.value_cents,
                                         source="Initial entry",
                                         notes="Value at the time it was recorded"))
            db.session.flush()
            _sync_value(holding)
            db.session.commit()
            flash(f'Created {holding.name}', 'success')
            return redirect(url_for('main.holding_details', id=holding.id))
        for p in problems:
            flash(p, 'error')
    elif request.method == 'POST':
        flash('There were errors in your form submission. Please check below.', 'error')

    return render_template('manage_holding.html', form=form, htype=htype,
                           side_meta=SIDE_META[side], holding=None,
                           custom_rows=_custom_rows() if request.method == 'POST' else [],
                           title=f"Add {htype.label if not htype.custom else 'a custom ' + SIDE_META[side]['singular'].lower()}",
                           active_page='assets')


@bp.route('/holding/edit/<int:id>', methods=['GET', 'POST'])
@bp.route('/asset/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_holding(id):
    holding = Holding.query.get_or_404(id)
    current = holding.htype
    # ?type=<code> switches type within the same side; matching fields carry
    # over and the rest move into notes, so a change of type loses nothing.
    htype = get_type(holding.side, request.args.get('type', holding.type_code)) or current
    if htype is None:
        abort(404)
    form = build_holding_form(htype)()
    _form_choices(form, holding)

    leftovers = []
    if htype is not current and not (current and current.custom):
        for key, value in (holding.attributes or {}).items():
            if htype.field(key) is None:
                label = current.field(key).label if current and current.field(key) else key
                leftovers.append(f"{label}: {value}")

    if request.method == 'GET':
        _prefill(form, holding, htype)

    old_value = holding.value_cents
    if form.validate_on_submit():
        problems = _save_holding(holding, form, htype, leftovers)
        if not problems:
            if holding.value_cents != old_value:
                db.session.add(Valuation(holding_id=holding.id, date=date.today(),
                                         value_cents=holding.value_cents,
                                         source="Manual update"))
            db.session.commit()
            flash(f'Updated {holding.name}', 'success')
            return redirect(url_for('main.holding_details', id=holding.id))
        db.session.rollback()
        for p in problems:
            flash(p, 'error')
    elif request.method == 'POST':
        flash('Update failed. Please correct the errors below.', 'error')

    custom_rows = (holding.attributes or {}).get("fields", []) if htype.custom else []
    if request.method == 'POST' and htype.custom:
        custom_rows = _custom_rows()
    return render_template('manage_holding.html', form=form, htype=htype,
                           side_meta=SIDE_META[holding.side], holding=holding,
                           other_types=types_for(holding.side), leftovers=leftovers,
                           custom_rows=custom_rows,
                           title=f"Edit {holding.name}", active_page='assets')


@bp.route('/holding/delete/<int:id>')
@bp.route('/asset/delete/<int:id>')
@login_required
def delete_holding(id):
    holding = Holding.query.get_or_404(id)
    try:
        db.session.delete(holding)
        db.session.commit()
        flash(f'Deleted {holding.name}', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Could not delete: other records still point at this item.', 'error')
    return redirect(url_for('main.holdings_view'))


@bp.route('/holding/<int:id>/verify', methods=['POST'])
@login_required
def verify_holding(id):
    holding = Holding.query.get_or_404(id)
    holding.mark_verified()
    db.session.commit()
    flash(f'Marked {holding.name} as verified today.', 'success')
    return redirect(request.referrer or url_for('main.holding_details', id=id))


# --- VALUATIONS ----------------------------------------------------------------

@bp.route('/holding/<int:id>/valuation', methods=['POST'])
@bp.route('/asset/<int:id>/appraise', methods=['POST'])
@login_required
def add_valuation(id):
    holding = Holding.query.get_or_404(id)
    form = ValuationForm()
    if form.validate_on_submit():
        db.session.add(Valuation(holding_id=holding.id, date=form.date.data,
                                 value_cents=form.value.data, source=form.source.data,
                                 notes=form.notes.data))
        db.session.flush()
        _sync_value(holding)
        db.session.commit()
        flash('Valuation added.', 'success')
    else:
        flash('Valuation not saved: ' + '; '.join(
            e for errs in form.errors.values() for e in errs), 'error')
    return redirect(url_for('main.holding_details', id=id))


@bp.route('/valuation/<int:id>/edit', methods=['POST'])
@login_required
def edit_valuation(id):
    valuation = Valuation.query.get_or_404(id)
    form = ValuationForm()
    if form.validate_on_submit():
        valuation.date = form.date.data
        valuation.value_cents = form.value.data
        valuation.source = form.source.data
        valuation.notes = form.notes.data
        holding = valuation.holding
        if valuation.source == "Purchase" and holding.htype and holding.htype.field("purchase_date"):
            attrs = dict(holding.attributes or {})
            attrs['purchase_date'] = valuation.date.isoformat()
            attrs['purchase_price'] = valuation.value_cents
            holding.attributes = attrs
        db.session.flush()
        _sync_value(holding)
        db.session.commit()
        flash('Valuation updated.', 'success')
    else:
        flash('Invalid data submitted for valuation update.', 'error')
    return redirect(url_for('main.holding_details', id=valuation.holding_id))


@bp.route('/valuation/<int:id>/delete', methods=['POST'])
@login_required
def delete_valuation(id):
    valuation = Valuation.query.get_or_404(id)
    holding = valuation.holding
    if valuation.source == "Purchase":
        attrs = dict(holding.attributes or {})
        attrs.pop('purchase_date', None)
        attrs.pop('purchase_price', None)
        holding.attributes = attrs
    db.session.delete(valuation)
    db.session.flush()
    _sync_value(holding)
    db.session.commit()
    flash('Valuation deleted.', 'success')
    return redirect(url_for('main.holding_details', id=holding.id))


# --- BENEFICIARY SHARES --------------------------------------------------------

def _designation_people(form):
    form.person_id.choices = [(p.id, p.name) for p in Person.query.order_by(Person.name).all()]


@bp.route('/holding/<int:id>/designation', methods=['POST'])
@login_required
def add_designation(id):
    holding = Holding.query.get_or_404(id)
    form = DesignationForm()
    _designation_people(form)
    if form.validate_on_submit():
        db.session.add(BeneficiaryDesignation(
            holding_id=holding.id, person_id=form.person_id.data,
            percentage=form.percentage.data, kind=form.kind.data,
            notes=form.notes.data or None))
        try:
            db.session.commit()
            flash('Share added.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('That person already has a share of this kind on this item - edit it instead.', 'error')
    else:
        flash('Share not saved: ' + '; '.join(
            e for errs in form.errors.values() for e in errs), 'error')
    return redirect(url_for('main.holding_details', id=id) + '#beneficiaries')


@bp.route('/designation/<int:id>/edit', methods=['POST'])
@login_required
def edit_designation(id):
    d = BeneficiaryDesignation.query.get_or_404(id)
    form = DesignationForm()
    _designation_people(form)
    if form.validate_on_submit():
        d.person_id = form.person_id.data
        d.percentage = form.percentage.data
        d.kind = form.kind.data
        d.notes = form.notes.data or None
        try:
            db.session.commit()
            flash('Share updated.', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('That person already has a share of this kind on this item.', 'error')
    else:
        flash('Share not saved: ' + '; '.join(
            e for errs in form.errors.values() for e in errs), 'error')
    return redirect(url_for('main.holding_details', id=d.holding_id) + '#beneficiaries')


@bp.route('/designation/<int:id>/delete', methods=['POST'])
@login_required
def delete_designation(id):
    d = BeneficiaryDesignation.query.get_or_404(id)
    holding_id = d.holding_id
    db.session.delete(d)
    db.session.commit()
    flash('Share removed.', 'success')
    return redirect(url_for('main.holding_details', id=holding_id) + '#beneficiaries')


# --- CONTACTS --------------------------------------------------------------------

def _person_from_form(person, form):
    person.name = form.name.data
    person.kind = form.kind.data
    person.email = form.email.data
    person.phone = form.phone.data
    attrs = dict(person.attributes or {})
    for key in ('address', 'notes'):
        value = getattr(form, key).data
        if value:
            attrs[key] = value
        else:
            attrs.pop(key, None)
    person.attributes = attrs
    person.set_roles(form.roles.data)


@bp.route('/contact/new', methods=['GET', 'POST'])
@login_required
def create_person():
    form = PersonForm()
    if request.method == 'GET' and request.args.get('role'):
        form.roles.data = [request.args.get('role')]

    if form.validate_on_submit():
        person = Person()
        _person_from_form(person, form)
        db.session.add(person)
        db.session.commit()
        flash(f'Contact {person.name} added.', 'success')
        return redirect(url_for('main.contacts_view'))

    return render_template('manage_person.html', form=form, title="Add Contact", active_page='contacts')


@bp.route('/contact/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_person(id):
    person = Person.query.get_or_404(id)
    form = PersonForm(obj=person)

    if request.method == 'GET':
        form.roles.data = person.role_codes
        form.address.data = (person.attributes or {}).get('address', '')
        form.notes.data = (person.attributes or {}).get('notes', '')

    if form.validate_on_submit():
        _person_from_form(person, form)
        db.session.commit()
        flash(f'Updated contact {person.name}.', 'success')
        return redirect(url_for('main.contacts_view'))

    return render_template('manage_person.html', form=form, person=person,
                           title="Edit Contact", active_page='contacts')


@bp.route('/contact/delete/<int:id>')
@login_required
def delete_person(id):
    person = Person.query.get_or_404(id)
    if person.designations:
        flash(f'{person.name} still has beneficiary shares on '
              f'{len(person.designations)} item(s). Reassign or remove those first.', 'error')
        return redirect(url_for('main.contacts_view'))
    try:
        db.session.delete(person)
        db.session.commit()
        flash(f'Deleted contact {person.name}.', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Could not delete: this contact is still assigned to an item or entity.', 'error')
    return redirect(url_for('main.contacts_view'))


@bp.route('/contact/<int:id>/verify', methods=['POST'])
@login_required
def verify_person(id):
    person = Person.query.get_or_404(id)
    person.mark_verified()
    db.session.commit()
    flash(f'Marked {person.name} as verified today.', 'success')
    return redirect(request.referrer or url_for('main.contacts_view'))


# --- SUB-ITEMS (offered on every holding) -----------------------------------------

SUBITEMS = {
    'structure': {'form': StructureForm, 'model': PropertyStructure,
                  'title': 'Add Structure / Accommodation'},
    'location': {'form': LocationPointForm, 'model': LocationPoint,
                 'title': 'Drop Location Pin'},
    'bill': {'form': RecurringBillForm, 'model': RecurringBill,
             'title': 'Add Recurring Bill'},
    'vendor': {'form': HoldingVendorForm, 'model': HoldingVendor,
               'title': 'Assign Contact'},
}


@bp.route('/holding/<int:id>/<string:subitem_type>/new', methods=['GET', 'POST'])
@login_required
def manage_subitem(id, subitem_type):
    holding = Holding.query.get_or_404(id)
    cfg = SUBITEMS.get(subitem_type)
    if cfg is None:
        flash('Unknown item type.', 'error')
        return redirect(url_for('main.holding_details', id=id))

    form = cfg['form']()
    if subitem_type == 'vendor':
        people = Person.query.order_by(Person.name).all()
        form.person_id.choices = [
            (p.id, f"{p.name} ({', '.join(p.role_labels)})" if p.roles else p.name)
            for p in people]

    if form.validate_on_submit():
        item = cfg['model']()
        item.holding_id = holding.id
        form.populate_obj(item)
        if subitem_type == 'bill' and item.amount_cents is None:
            item.amount_cents = 0
        db.session.add(item)
        db.session.commit()
        flash(f'{cfg["title"]} saved.', 'success')
        return redirect(url_for('main.holding_details', id=id))

    return render_template('manage_subitem.html', form=form, title=cfg['title'],
                           holding=holding, subitem_type=subitem_type, active_page='assets')


@bp.route('/holding/<int:holding_id>/<string:subitem_type>/<int:item_id>/delete')
@login_required
def delete_subitem(holding_id, subitem_type, item_id):
    cfg = SUBITEMS.get(subitem_type)
    if cfg:
        item = cfg['model'].query.get_or_404(item_id)
        if item.holding_id == holding_id:
            db.session.delete(item)
            db.session.commit()
            flash('Item removed.', 'success')
    return redirect(url_for('main.holding_details', id=holding_id))


# --- THE TRUST (root entity) AND ITS ADD-ONS ----------------------------------------

@bp.route('/trust/edit', methods=['GET', 'POST'])
@login_required
def edit_trust_profile():
    root = get_root_entity()
    form = TrustProfileForm(obj=root)
    died_before = root.date_death_actual

    if form.validate_on_submit():
        form.populate_obj(root)
        db.session.commit()
        flash('Trust details updated.', 'success')
        # Filling in the date of passing offers the transition playbook.
        pb = playbook_service.death_playbook()
        if root.date_death_actual and root.date_death_actual != died_before and pb:
            if not any(d == root.date_death_actual.isoformat()
                       for d, _ in playbook_service.runs(pb)):
                return redirect(url_for('manage.run_playbook', id=pb.id,
                                        date=root.date_death_actual.isoformat(), offered=1))
        return redirect(url_for('main.details_view'))

    return render_template('manage_trust.html', form=form, title="Edit Trust Details", active_page='details')


def _entity_people(form):
    form.person_id.choices = [(0, '—')] + [
        (p.id, p.name) for p in Person.query.order_by(Person.name).all()]


@bp.route('/entity/new', methods=['GET', 'POST'])
@bp.route('/entity/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def manage_entity(id=None):
    root = get_root_entity()
    entity = Entity.query.get_or_404(id) if id else None
    if entity is not None and entity.is_root:
        return redirect(url_for('manage.edit_trust_profile'))
    form = EntityForm(obj=entity)
    _entity_people(form)
    if request.method == 'GET' and entity is not None:
        form.person_id.data = entity.person_id or 0

    if form.validate_on_submit():
        if entity is None:
            entity = Entity(is_root=False, parent_id=root.id)
            db.session.add(entity)
        entity.kind = form.kind.data
        entity.name = form.name.data
        entity.person_id = (form.person_id.data or None) if form.kind.data == 'individual' else None
        entity.date_established = form.date_established.data
        entity.notes = form.notes.data or None
        db.session.commit()
        flash(f'Saved {entity.name}.', 'success')
        return redirect(url_for('main.details_view'))

    return render_template('manage_entity.html', form=form, entity=entity, root=root,
                           title=f"Edit {entity.name}" if entity else "Add an entity under the trust",
                           active_page='details')


@bp.route('/entity/<int:id>/delete', methods=['POST'])
@login_required
def delete_entity(id):
    entity = Entity.query.get_or_404(id)
    if entity.is_root:
        flash('The trust is the root of the estate and cannot be deleted.', 'error')
    elif entity.holdings:
        flash(f'{entity.name} still holds {len(entity.holdings)} item(s). Move them first.', 'error')
    else:
        db.session.delete(entity)
        db.session.commit()
        flash(f'Removed {entity.name}.', 'success')
    return redirect(url_for('main.details_view'))


# --- EVENTS ------------------------------------------------------------------------

def _event_choices(form):
    people = Person.query.order_by(Person.name).all()
    form.assignee_id.choices = [(0, '— Nobody yet —')] + [(p.id, p.name) for p in people]
    form.person_id.choices = [(0, '—')] + [(p.id, p.name) for p in people]
    form.holding_id.choices = [(0, '—')] + [
        (h.id, f"{h.icon} {h.name}") for h in Holding.query.order_by(Holding.name).all()]
    root = get_root_entity()
    form.entity_id.choices = [(0, '—'), (root.id, f"{root.name} (the trust)")] + [
        (e.id, f"{e.name} · {e.kind_label}") for e in addon_entities()]


def _event_from_form(event, form):
    event.title = form.title.data
    event.kind = form.kind.data
    event.date = form.date.data
    event.phase = form.phase.data
    event.assignee_id = form.assignee_id.data or None
    event.description = (form.description.data or '').strip() or None
    event.holding_id = form.holding_id.data or None
    event.entity_id = form.entity_id.data or None
    event.person_id = form.person_id.data or None
    event.repeat_every = form.repeat_every.data if form.repeat_unit.data else None
    event.repeat_unit = form.repeat_unit.data or None


def _back(default):
    nxt = request.values.get('next') or ''
    # Only ever bounce back inside this app.
    return nxt if nxt.startswith('/') and not nxt.startswith('//') else default


@bp.route('/event/new', methods=['GET', 'POST'])
@login_required
def create_event():
    form = EventForm()
    _event_choices(form)
    if request.method == 'GET':
        for key in ('holding_id', 'entity_id', 'person_id', 'assignee_id'):
            if request.args.get(key, type=int):
                getattr(form, key).data = request.args.get(key, type=int)
        if request.args.get('kind'):
            form.kind.data = request.args['kind']
        if request.args.get('phase'):
            form.phase.data = request.args['phase']
        if request.args.get('date'):
            try:
                form.date.data = date.fromisoformat(request.args['date'])
            except ValueError:
                pass

    if form.validate_on_submit():
        event = Event()
        _event_from_form(event, form)
        db.session.add(event)
        db.session.flush()
        if form.done.data:
            event_service.complete(f"event:{event.id}")
        db.session.commit()
        flash(f'Added "{event.title}".', 'success')
        return redirect(_back(url_for('main.now')))
    return render_template('manage_event.html', form=form, event=None,
                           title='Add to the timeline', active_page='now')


@bp.route('/event/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(id):
    event = Event.query.get_or_404(id)
    form = EventForm(obj=event)
    _event_choices(form)
    if request.method == 'GET':
        for key in ('holding_id', 'entity_id', 'person_id', 'assignee_id'):
            getattr(form, key).data = getattr(event, key) or 0
        form.repeat_unit.data = event.repeat_unit or ''
        form.done.data = event.is_done

    if form.validate_on_submit():
        was_done = event.is_done
        _event_from_form(event, form)
        if form.done.data and not was_done:
            event_service.complete(f"event:{event.id}")
        elif not form.done.data and was_done:
            event.done_at = None
        db.session.commit()
        flash(f'Saved "{event.title}".', 'success')
        return redirect(_back(url_for('main.now')))
    return render_template('manage_event.html', form=form, event=event,
                           title='Edit event', active_page='now')


@bp.route('/event/<int:id>/delete', methods=['POST'])
@login_required
def delete_event(id):
    event = Event.query.get_or_404(id)
    if event.source and not event.source.startswith('playbook:'):
        # A derived item's row is what keeps the feed from offering it again.
        # Deleting it would bring the item straight back, so it is closed instead.
        if not event.is_done:
            event.done_at = date.today()
        db.session.commit()
        flash('That item is worked out from your records, so it was marked done '
              'rather than deleted.', 'success')
    else:
        db.session.delete(event)
        db.session.commit()
        flash(f'Deleted "{event.title}".', 'success')
    return redirect(_back(url_for('main.now')))


@bp.route('/timeline/act', methods=['POST'])
@login_required
def timeline_action():
    """The one-tap buttons. `key` is a row key: event:<id> or a feed source."""
    key = request.form.get('key', '')
    action = request.form.get('action', '')
    back = _back(url_for('main.now'))
    try:
        if action == 'done':
            event, spawned = event_service.complete(key)
            msg = f'Done: {event.title}.'
            if spawned:
                msg += f' Next one is on {spawned.date.isoformat()}.'
        elif action == 'snooze':
            event = event_service.snooze(key)
            msg = f'Snoozed to {event.date.isoformat()}: {event.title}.'
        elif action == 'reopen':
            event = event_service.reopen(key)
            msg = f'Reopened: {event.title}.'
        elif action == 'note':
            event = event_service.materialise(key)
            db.session.commit()
            return redirect(url_for('manage.edit_event', id=event.id, next=back))
        else:
            abort(400)
    except event_service.NotFound:
        db.session.rollback()
        flash('That item no longer applies - the record behind it has changed.', 'error')
        return redirect(back)
    db.session.commit()
    flash(msg, 'success')
    return redirect(back)


# --- PLAYBOOKS -----------------------------------------------------------------------

@bp.route('/playbook/new', methods=['GET', 'POST'])
@bp.route('/playbook/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def manage_playbook(id=None):
    pb = Playbook.query.get_or_404(id) if id else None
    form = PlaybookForm(obj=pb)
    if request.method == 'GET' and pb is not None:
        form.trigger.data = pb.trigger or ''
    if form.validate_on_submit():
        if pb is None:
            pb = Playbook()
            db.session.add(pb)
        pb.name = form.name.data
        pb.description = form.description.data or None
        pb.trigger = form.trigger.data or None
        db.session.commit()
        flash(f'Saved {pb.name}.', 'success')
        return redirect(url_for('main.playbook_view', id=pb.id))
    return render_template('manage_playbook.html', form=form, playbook=pb,
                           title=f'Edit {pb.name}' if pb else 'New playbook',
                           active_page='playbooks')


@bp.route('/playbook/<int:id>/delete', methods=['POST'])
@login_required
def delete_playbook(id):
    pb = Playbook.query.get_or_404(id)
    db.session.delete(pb)
    db.session.commit()
    flash(f'Deleted {pb.name}. Events it already created are kept.', 'success')
    return redirect(url_for('main.playbooks_view'))


@bp.route('/playbook/default', methods=['POST'])
@login_required
def install_default_playbook():
    pb = default_playbook.install(db.session)
    db.session.commit()
    flash('Added a fresh copy of the default playbook.', 'success')
    return redirect(url_for('main.playbook_view', id=pb.id))


@bp.route('/playbook/<int:id>/step/new', methods=['GET', 'POST'])
@bp.route('/playbook/<int:id>/step/<int:step_id>/edit', methods=['GET', 'POST'])
@login_required
def manage_step(id, step_id=None):
    pb = Playbook.query.get_or_404(id)
    step = PlaybookStep.query.get_or_404(step_id) if step_id else None
    if step is not None and step.playbook_id != pb.id:
        abort(404)
    form = PlaybookStepForm(obj=step)
    if request.method == 'GET' and step is not None:
        form.who_role.data = step.who_role or ''
    if form.validate_on_submit():
        if step is None:
            step = PlaybookStep(playbook_id=pb.id,
                                position=max((s.position for s in pb.steps), default=-1) + 1)
            db.session.add(step)
        step.offset_days = form.offset_days.data or 0
        step.title = form.title.data
        step.kind = form.kind.data
        step.who_role = form.who_role.data or None
        step.instructions = form.instructions.data or None
        step.document_type = form.document_type.data or None
        db.session.commit()
        flash('Step saved.', 'success')
        return redirect(url_for('main.playbook_view', id=pb.id) + f'#step-{step.id}')
    return render_template('manage_step.html', form=form, playbook=pb, step=step,
                           title='Edit step' if step else 'Add a step',
                           active_page='playbooks')


@bp.route('/playbook/<int:id>/step/<int:step_id>/delete', methods=['POST'])
@login_required
def delete_step(id, step_id):
    step = PlaybookStep.query.get_or_404(step_id)
    if step.playbook_id != id:
        abort(404)
    db.session.delete(step)
    db.session.commit()
    flash('Step removed.', 'success')
    return redirect(url_for('main.playbook_view', id=id))


@bp.route('/playbook/<int:id>/run', methods=['GET', 'POST'])
@login_required
def run_playbook(id):
    pb = Playbook.query.get_or_404(id)
    form = RunPlaybookForm()
    if request.method == 'GET' and request.args.get('date'):
        try:
            form.trigger_date.data = date.fromisoformat(request.args['date'])
        except ValueError:
            pass
    if form.validate_on_submit():
        created, skipped = playbook_service.run(pb, form.trigger_date.data)
        db.session.commit()
        msg = f'{len(created)} events added to the timeline from "{pb.name}".'
        if skipped:
            msg += f' {skipped} were already there from an earlier run on this date.'
        flash(msg, 'success')
        return redirect(url_for('main.now', phase='transition'))
    preview_date = form.trigger_date.data
    return render_template('run_playbook.html', form=form, playbook=pb,
                           preview_date=preview_date,
                           already=[d for d, _ in playbook_service.runs(pb)],
                           offered=request.args.get('offered'),
                           disclaimer=default_playbook.DISCLAIMER,
                           title=f'Run {pb.name}', active_page='playbooks')
