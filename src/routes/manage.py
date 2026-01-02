import json
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from src.extensions import db
from src.models import Asset, Person, Appraisal, PropertyStructure, LocationPoint, RecurringBill, AssetVendor
from src.forms import (
    get_form_class, AppraisalForm, PersonForm, 
    StructureForm, LocationPointForm, RecurringBillForm, AssetVendorForm
)
from src.services.auth_service import login_required

bp = Blueprint('manage', __name__, url_prefix='/manage')

ASSET_TYPES_META = [
    ('RealEstate', 'Real Estate Property', '🏠'),
    ('Bank', 'Bank Account', '🏦'),
    ('Investment', 'Investment Portfolio', '📈'),
    ('Vehicle', 'Vehicle', '🚗'),
    ('Jewelry', 'Jewelry / Watch', '💎'),
    ('Art', 'Art / Collectible', '🎨'),
    ('Liability', 'Loan / Debt', '💳'),
    ('Other', 'Other Asset', '📦')
]

# --- ASSET MANAGEMENT ---

@bp.route('/asset/select-type')
@login_required
def select_type():
    return render_template('select_type.html', asset_types=ASSET_TYPES_META, active_page='assets')

@bp.route('/asset/new/<type_code>', methods=['GET', 'POST'])
@login_required
def create_asset_step2(type_code):
    FormClass = get_form_class(type_code)
    form = FormClass()
    
    people = Person.query.all()
    form.owner_id.choices = [(0, '--- No Individual Owner ---')] + [(p.id, p.name) for p in people]

    if form.validate_on_submit():
        asset = Asset()
        asset.asset_type = type_code
        save_asset_from_form(asset, form)
        
        db.session.add(asset)
        db.session.commit()
        
        # Smart Appraisal Creation Logic
        if hasattr(form, 'purchase_date') and form.purchase_date.data:
            try:
                p_date = datetime.strptime(form.purchase_date.data, '%Y-%m-%d').date()
                p_price_field = getattr(form, 'purchase_price', None)
                p_val = p_price_field.data if (p_price_field and p_price_field.data) else 0.0
                
                purchase_appraisal = Appraisal(
                    asset_id=asset.id,
                    date=p_date,
                    value=p_val,
                    source="Purchase",
                    notes="Original Purchase Price"
                )
                db.session.add(purchase_appraisal)
            except ValueError:
                pass

        if asset.value_estimated != 0:
            skip = False
            if hasattr(form, 'purchase_date') and form.purchase_date.data:
                 if form.purchase_date.data == date.today().isoformat() and \
                    getattr(form, 'purchase_price', None) and \
                    getattr(form, 'purchase_price').data == asset.value_estimated:
                     skip = True

            if not skip:
                current_appraisal = Appraisal(
                    asset_id=asset.id,
                    date=date.today(),
                    value=asset.value_estimated,
                    source="Initial Entry",
                    notes="Current value at time of recording"
                )
                db.session.add(current_appraisal)

        db.session.commit()
        flash(f'Created {asset.name}', 'success')
        return redirect(url_for('main.assets_view'))
    
    elif request.method == 'POST':
        flash('There were errors in your form submission. Please check below.', 'error')

    form.asset_type.data = type_code
    return render_template('manage_asset.html', form=form, title=f"Add {type_code}", type_code=type_code, active_page='assets')

@bp.route('/asset/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def manage_asset(id):
    asset = Asset.query.get_or_404(id)
    FormClass = get_form_class(asset.asset_type)
    form = FormClass(obj=asset)

    if request.method == 'GET':
        if hasattr(form, 'current_value'):
            form.current_value.data = abs(asset.value_estimated)
        if hasattr(form, 'outstanding_balance'):
            form.outstanding_balance.data = abs(asset.value_estimated)
            
        if asset.attributes:
            for field_name in asset.attributes:
                if hasattr(form, field_name):
                    getattr(form, field_name).data = asset.attributes[field_name]

    people = Person.query.all()
    form.owner_id.choices = [(0, '--- No Individual Owner ---')] + [(p.id, p.name) for p in people]

    if form.validate_on_submit():
        save_asset_from_form(asset, form)
        db.session.commit()
        flash(f'Updated {asset.name}', 'success')
        return redirect(url_for('main.asset_details', id=asset.id))
    
    elif request.method == 'POST':
        flash('Update failed. Please correct the errors below.', 'error')

    return render_template('manage_asset.html', form=form, title=f"Edit {asset.asset_type}", type_code=asset.asset_type, active_page='assets')

@bp.route('/asset/delete/<int:id>')
@login_required
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    try:
        db.session.delete(asset)
        db.session.commit()
        flash(f'Deleted {asset.name}', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting asset.', 'error')
    return redirect(url_for('main.assets_view'))

# --- APPRAISALS ---

@bp.route('/asset/<int:id>/appraise', methods=['POST'])
@login_required
def add_appraisal(id):
    asset = Asset.query.get_or_404(id)
    form = AppraisalForm()
    if form.validate_on_submit():
        appraisal = Appraisal(
            asset_id=asset.id,
            date=form.date.data,
            value=form.value.data,
            source=form.source.data,
            notes=form.notes.data
        )
        db.session.add(appraisal)
        if form.date.data:
            asset.value_estimated = form.value.data
        try:
            db.session.commit()
            flash('Valuation added and asset updated.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'error')
    return redirect(url_for('main.asset_details', id=id))

@bp.route('/appraisal/<int:id>/edit', methods=['POST'])
@login_required
def edit_appraisal(id):
    appraisal = Appraisal.query.get_or_404(id)
    form = AppraisalForm()
    if form.validate_on_submit():
        appraisal.date = form.date.data
        appraisal.value = form.value.data
        appraisal.source = form.source.data
        appraisal.notes = form.notes.data
        latest = Appraisal.query.filter_by(asset_id=appraisal.asset_id).order_by(Appraisal.date.desc()).first()
        if latest and appraisal.id == latest.id:
             appraisal.asset.value_estimated = form.value.data
        if appraisal.source == "Purchase":
            attrs = dict(appraisal.asset.attributes or {})
            attrs['purchase_date'] = appraisal.date.isoformat()
            attrs['purchase_price'] = appraisal.value
            appraisal.asset.attributes = attrs
        try:
            db.session.commit()
            flash('Valuation updated successfully.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating valuation: {str(e)}', 'error')
    else:
        flash('Invalid data submitted for valuation update.', 'error')
    return redirect(url_for('main.asset_details', id=appraisal.asset_id))

@bp.route('/appraisal/<int:id>/delete', methods=['POST'])
@login_required
def delete_appraisal(id):
    appraisal = Appraisal.query.get_or_404(id)
    asset_id = appraisal.asset_id
    is_purchase = (appraisal.source == "Purchase")
    try:
        db.session.delete(appraisal)
        if is_purchase:
            asset = Asset.query.get(asset_id)
            attrs = dict(asset.attributes or {})
            attrs.pop('purchase_date', None)
            attrs.pop('purchase_price', None)
            asset.attributes = attrs
        db.session.commit()
        latest = Appraisal.query.filter_by(asset_id=asset_id).order_by(Appraisal.date.desc()).first()
        asset = Asset.query.get(asset_id)
        if latest:
            asset.value_estimated = latest.value
        db.session.commit()
        flash('Valuation deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting valuation: {str(e)}', 'error')
    return redirect(url_for('main.asset_details', id=asset_id))

# --- CONTACTS ---

@bp.route('/contact/new', methods=['GET', 'POST'])
@login_required
def create_person():
    form = PersonForm()
    if request.method == 'GET' and request.args.get('role'):
        form.role.data = request.args.get('role')

    if form.validate_on_submit():
        person = Person()
        person.name = form.name.data
        person.role = form.role.data
        person.email = form.email.data
        person.phone = form.phone.data
        attrs = {}
        if form.address.data: attrs['address'] = form.address.data
        if form.notes.data: attrs['notes'] = form.notes.data
        person.attributes = attrs
        
        db.session.add(person)
        try:
            db.session.commit()
            flash(f'Contact {person.name} added successfully.', 'success')
            return redirect(url_for('main.details_view'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating contact: {str(e)}', 'error')

    return render_template('manage_person.html', form=form, title="Add Contact", active_page='details')

@bp.route('/contact/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_person(id):
    person = Person.query.get_or_404(id)
    form = PersonForm(obj=person)

    if request.method == 'GET':
        if person.attributes:
            form.address.data = person.attributes.get('address', '')
            form.notes.data = person.attributes.get('notes', '')

    if form.validate_on_submit():
        person.name = form.name.data
        person.role = form.role.data
        person.email = form.email.data
        person.phone = form.phone.data
        
        attrs = {}
        if form.address.data: attrs['address'] = form.address.data
        if form.notes.data: attrs['notes'] = form.notes.data
        person.attributes = attrs

        try:
            db.session.commit()
            flash(f'Updated contact {person.name}.', 'success')
            return redirect(url_for('main.details_view'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating contact: {str(e)}', 'error')

    return render_template('manage_person.html', form=form, title="Edit Contact", active_page='details')

@bp.route('/contact/delete/<int:id>')
@login_required
def delete_person(id):
    person = Person.query.get_or_404(id)
    try:
        db.session.delete(person)
        db.session.commit()
        flash(f'Deleted contact {person.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting contact. Check if they are linked to assets.', 'error')
    return redirect(url_for('main.details_view'))

# --- PHASE 5: SUB-ITEMS (Structures, Pins, Bills, Vendors) ---

@bp.route('/asset/<int:id>/<string:subitem_type>/new', methods=['GET', 'POST'])
@login_required
def manage_subitem(id, subitem_type):
    asset = Asset.query.get_or_404(id)
    
    # Logic Dispatcher
    config = {
        'structure': {
            'form': StructureForm, 'model': PropertyStructure, 'title': 'Add Structure / Accommodation', 'is_vendor': False
        },
        'location': {
            'form': LocationPointForm, 'model': LocationPoint, 'title': 'Drop Location Pin', 'is_vendor': False
        },
        'bill': {
            'form': RecurringBillForm, 'model': RecurringBill, 'title': 'Add Recurring Bill', 'is_vendor': False
        },
        'vendor': {
            'form': AssetVendorForm, 'model': AssetVendor, 'title': 'Assign Vendor', 'is_vendor': True
        }
    }
    
    if subitem_type not in config:
        flash('Unknown item type.', 'error')
        return redirect(url_for('main.asset_details', id=id))
        
    cfg = config[subitem_type]
    form = cfg['form']()
    
    # Special Handling for Vendors (Populate SelectField)
    if cfg['is_vendor']:
        people = Person.query.order_by(Person.name).all()
        form.person_id.choices = [(p.id, f"{p.name} ({p.role})") for p in people]

    if form.validate_on_submit():
        item = cfg['model']()
        item.asset_id = asset.id
        form.populate_obj(item) # Auto-map form fields to model
        
        db.session.add(item)
        try:
            db.session.commit()
            flash(f'{cfg["title"]} saved successfully.', 'success')
            return redirect(url_for('main.asset_details', id=id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving item: {str(e)}', 'error')
            
    return render_template('manage_subitem.html', form=form, title=cfg['title'], asset=asset, subitem_type=subitem_type, active_page='assets')

@bp.route('/asset/<int:asset_id>/<string:subitem_type>/<int:item_id>/delete')
@login_required
def delete_subitem(asset_id, subitem_type, item_id):
    # Mapping
    models = {
        'structure': PropertyStructure,
        'location': LocationPoint,
        'bill': RecurringBill,
        'vendor': AssetVendor
    }
    
    if subitem_type in models:
        item = models[subitem_type].query.get_or_404(item_id)
        if item.asset_id == asset_id:
            db.session.delete(item)
            db.session.commit()
            flash('Item removed.', 'success')
    
    return redirect(url_for('main.asset_details', id=asset_id))

# --- HELPER ---
def save_asset_from_form(asset, form):
    asset.name = form.name.data
    asset.is_in_trust = form.is_in_trust.data
    owner_id = form.owner_id.data
    asset.owner_id = owner_id if owner_id != 0 else None
    
    val = 0.0
    if hasattr(form, 'outstanding_balance'):
        val = -(form.outstanding_balance.data or 0.0)
    elif hasattr(form, 'current_value'):
        val = form.current_value.data or 0.0
    asset.value_estimated = val

    core_columns = ['name', 'is_in_trust', 'owner_id', 'csrf_token', 'submit', 'asset_type', 'current_value', 'outstanding_balance']
    
    attrs = {}
    for field in form:
        if field.name not in core_columns:
            attrs[field.name] = field.data
            
    asset.attributes = attrs