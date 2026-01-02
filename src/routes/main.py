from flask import Blueprint, render_template
from src.services.auth_service import login_required
from src.models import Person, Asset, Milestone

bp = Blueprint('main', __name__)

@bp.route('/')
@login_required
def dashboard():
    # 1. Fetch Data
    all_assets = Asset.query.all()
    
    # 2. Calculate Financials
    total_assets = sum(a.value_estimated for a in all_assets if a.value_estimated > 0)
    total_liabilities = sum(a.value_estimated for a in all_assets if a.value_estimated < 0)
    net_worth = total_assets + total_liabilities # Liabilities are negative, so we add
    
    # Count items
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
    # Only positive assets
    assets = Asset.query.filter(Asset.value_estimated >= 0).all()
    return render_template('assets.html', assets=assets, active_page='assets')

@bp.route('/liabilities')
@login_required
def liabilities_view():
    # Only negative assets (Debts)
    debts = Asset.query.filter(Asset.value_estimated < 0).all()
    return render_template('assets.html', assets=debts, is_liability=True, active_page='liabilities')

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