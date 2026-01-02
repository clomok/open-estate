import json # NEW IMPORT
from flask import Blueprint, render_template, redirect, url_for, flash, request
from src.extensions import db
from src.models import Asset, Person
from src.forms import AssetForm
from src.services.auth_service import login_required

bp = Blueprint('manage', __name__, url_prefix='/manage')

@bp.route('/asset/new', methods=['GET', 'POST'])
@bp.route('/asset/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def manage_asset(id=None):
    asset = None
    if id:
        asset = Asset.query.get_or_404(id)
        form = AssetForm(obj=asset)
        
        # Pre-fill the hidden field with existing attributes so JS can read them
        if asset.attributes:
            form.attributes_json.data = json.dumps(asset.attributes)
    else:
        form = AssetForm()

    people = Person.query.all()
    form.owner_id.choices = [(0, '--- No Individual Owner ---')] + [(p.id, p.name) for p in people]

    if form.validate_on_submit():
        if not asset:
            asset = Asset()
            db.session.add(asset)
        
        asset.name = form.name.data
        asset.asset_type = form.asset_type.data
        asset.value_estimated = form.value_estimated.data or 0.0
        asset.is_in_trust = form.is_in_trust.data
        
        owner_id = form.owner_id.data
        asset.owner_id = owner_id if owner_id != 0 else None
        
        # LOGIC CHANGE: Parse the JSON string from the hidden field
        try:
            raw_json = form.attributes_json.data
            if raw_json:
                asset.attributes = json.loads(raw_json)
            else:
                asset.attributes = {}
        except ValueError:
            # Fallback if something weird happens
            asset.attributes = {}
        
        try:
            db.session.commit()
            flash(f'Successfully saved {asset.name}', 'success')
            return redirect(url_for('main.assets_view'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving asset: {str(e)}', 'error')

    return render_template('manage_asset.html', form=form, title="Edit Asset" if id else "Add New Asset")

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