import json
from datetime import date
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
    
    # --- CHART DATA PREPARATION ---
    # 1. Collect all unique dates from all appraisals
    all_dates = set()
    for asset in all_assets:
        for app in asset.appraisals:
            all_dates.add(app.date)
    
    # Ensure the timeline extends to today
    all_dates.add(date.today())
    sorted_dates = sorted(list(all_dates))
    
    # 2. Build Datasets (One per asset)
    datasets = []
    
    # DISTINCT PALETTES
    # Cool colors for Assets (Greens, Blues, Purples, Teals)
    asset_colors = [
        '#16a34a', '#2563eb', '#9333ea', '#0891b2', '#0d9488', 
        '#4f46e5', '#059669', '#7c3aed', '#0284c7', '#65a30d'
    ]
    
    # Warm colors for Liabilities (Reds, Oranges, Pinks)
    liability_colors = [
        '#dc2626', '#ea580c', '#db2777', '#b91c1c', '#c2410c',
        '#be123c', '#991b1b', '#9a3412', '#831843', '#7f1d1d'
    ]
    
    # Counters to rotate through palettes
    a_idx = 0
    l_idx = 0
    
    for asset in all_assets:
        apps = sorted(asset.appraisals, key=lambda x: x.date)
        app_map = {a.date: a.value for a in apps}
        
        # Determine when this asset "started" (first appraisal date)
        start_date = apps[0].date if apps else date.max
        
        data_points = []
        current_val = 0.0
        
        for d in sorted_dates:
            if d in app_map:
                current_val = app_map[d]
            elif d < start_date:
                # If date is before the asset existed/was recorded, value is 0
                current_val = 0.0
            # else: keep current_val (Forward Fill logic)
            
            data_points.append(current_val)
        
        # Determine Color based on type (Positive vs Negative)
        if asset.value_estimated < 0:
            color = liability_colors[l_idx % len(liability_colors)]
            l_idx += 1
        else:
            color = asset_colors[a_idx % len(asset_colors)]
            a_idx += 1
            
        datasets.append({
            'id': asset.id,
            'label': asset.name,
            'data': data_points,
            'color': color,
            'type': asset.asset_type,
            'current_value': asset.value_estimated
        })
        
    chart_payload = {
        'dates': [d.isoformat() for d in sorted_dates],
        'datasets': datasets
    }

    return render_template('dashboard.html', 
                           active_page='overview',
                           net_worth=net_worth,
                           total_assets=total_assets,
                           total_liabilities=total_liabilities,
                           trust_count=trust_count,
                           chart_payload=chart_payload)

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