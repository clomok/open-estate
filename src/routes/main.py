import json
from flask import Blueprint, render_template
from src.services.auth_service import login_required
from src.models import Person, Asset, Milestone
from src.forms import AppraisalForm

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def dashboard():
    all_assets = Asset.query.all()
    total_assets = sum(a.value_estimated for a in all_assets if a.value_estimated > 0)
    total_liabilities = sum(a.value_estimated for a in all_assets if a.value_estimated < 0)
    net_worth = total_assets + total_liabilities
    trust_count = sum(1 for a in all_assets if a.is_in_trust)
    
    return render_template('dashboard.html', 
                           active_page='overview',
                           net_worth=net_worth,
                           total_assets=total_assets,
                           total_liabilities=total_liabilities,
                           trust_count=trust_count)

@bp.route('/assets')
@login_required
def assets_view():
    # Fetch all items sorted by name
    all_items = Asset.query.order_by(Asset.name).all()
    
    # Split them for display
    assets_list = [a for a in all_items if a.value_estimated >= 0]
    liabilities_list = [a for a in all_items if a.value_estimated < 0]
    
    return render_template('assets.html', 
                           assets=assets_list, 
                           liabilities=liabilities_list, 
                           active_page='assets')

# --- LIABILITIES ROUTE DELETED (Merged into above) ---

@bp.route('/asset/<int:id>')
@login_required
def asset_details(id):
    asset = Asset.query.get_or_404(id)
    form = AppraisalForm()
    
    history = sorted(asset.appraisals, key=lambda x: x.date)
    
    if not history:
        dates = [json.dumps(str(asset.attributes.get('purchase_date', 'Initial'))).strip('"')]
        values = [asset.value_estimated]
    else:
        dates = [h.date.strftime('%Y-%m-%d') for h in history]
        values = [h.value for h in history]
    
    return render_template('asset_details.html', 
                           asset=asset, 
                           form=form, 
                           chart_dates=dates, 
                           chart_values=values,
                           active_page='assets')

@bp.route('/planning')
@login_required
def planning_view():
    timeline = Milestone.query.order_by(Milestone.id).all()
    return render_template('planning.html', timeline=timeline, active_page='planning')

@bp.route('/details')
@login_required
def details_view():
    people = Person.query.all()
    return render_template('details.html', people=people, active_page='details')

@bp.route('/faq')
@login_required
def faq_view():
    return render_template('faq.html', active_page='faq')