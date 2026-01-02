import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from src.extensions import db
from src.models import Asset, Person, Appraisal
from src.forms import get_form_class, AppraisalForm
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
    ('Utility', 'Utility Account', '💡'),
    ('Other', 'Other Asset', '📦')
]

@bp.route('/asset/select-type')
@login_required
def select_type():
    # Added active_page
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
        flash(f'Created {asset.name}', 'success')
        return redirect(url_for('main.assets_view'))

    form.asset_type.data = type_code
    # Added active_page
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

    # Added active_page
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