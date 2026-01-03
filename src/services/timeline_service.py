from datetime import date, datetime
from flask import url_for
from src.models import Milestone, Task, RecurringBill, Asset, PropertyStructure, Appraisal

# Define icons here to be available for logic
ASSET_ICONS = {
    'RealEstate': '🏠',
    'Bank': '🏦',
    'Investment': '📈',
    'Vehicle': '🚗',
    'Jewelry': '💎',
    'Art': '🎨',
    'Liability': '💳',
    'Other': '📦'
}

def get_timeline_events(filter_types=None):
    """
    Aggregates all dated items into a standardized event list.
    Event Structure: {
        'date': date_obj,
        'title': str,
        'description': str,
        'type': str (financial, asset, maintenance, milestone, task),
        'type_label': str, # NEW: For UI Badge
        'icon': str,
        'link': str,
        'is_past': bool
    }
    """
    events = []
    today = date.today()
    
    # 1. MILESTONES
    if not filter_types or 'milestone' in filter_types:
        for m in Milestone.query.all():
            if m.date_event:
                # Handle datetime vs date
                d = m.date_event.date() if isinstance(m.date_event, datetime) else m.date_event
                events.append({
                    'date': d,
                    'title': m.title,
                    'description': m.description,
                    'type': 'milestone',
                    'type_label': 'Milestone',
                    'icon': '🚩',
                    'link': '#', # No edit UI for milestones yet
                    'is_past': d < today
                })

    # 2. RECURRING BILLS (Next Due Date)
    if not filter_types or 'financial' in filter_types:
        for b in RecurringBill.query.filter(RecurringBill.next_due_date != None).all():
            events.append({
                'date': b.next_due_date,
                'title': b.name,
                'description': f"Payee: {b.payee} (~${b.amount_estimated:.0f})",
                'type': 'financial',
                'type_label': 'Bill Due',
                'icon': '💳',
                'link': url_for('main.asset_details', id=b.asset_id) + '#tab-bills',
                'is_past': b.next_due_date < today
            })

    # 3. TASKS
    if not filter_types or 'task' in filter_types:
        for t in Task.query.filter(Task.due_date != None).all():
            d = t.due_date.date() if isinstance(t.due_date, datetime) else t.due_date
            events.append({
                'date': d,
                'title': t.title,
                'description': f"Status: {t.status}",
                'type': 'task',
                'type_label': 'Task',
                'icon': '✅',
                'link': url_for('main.asset_details', id=t.asset_id) if t.asset_id else '#',
                'is_past': d < today
            })

    # 4. ASSET HISTORY (Purchases & Appraisals)
    if not filter_types or 'history' in filter_types:
        for a in Asset.query.all():
            # Get specific icon or default
            icon_char = ASSET_ICONS.get(a.asset_type, '📦')

            # A. Purchase Date (from attributes)
            p_date_str = a.attributes.get('purchase_date')
            if p_date_str:
                try:
                    p_date = datetime.strptime(p_date_str, '%Y-%m-%d').date()
                    events.append({
                        'date': p_date,
                        'title': a.name,
                        'description': f"Acquired for estate.",
                        'type': 'asset',
                        'type_label': 'Purchased',
                        'icon': icon_char, # Updated to match asset
                        'link': url_for('main.asset_details', id=a.id),
                        'is_past': True
                    })
                except:
                    pass
            
            # B. Appraisals (History)
            for app in a.appraisals:
                events.append({
                    'date': app.date,
                    'title': a.name,
                    'description': f"Valued at ${app.value:,.0f} ({app.source})",
                    'type': 'history',
                    'type_label': 'Appraisal',
                    'icon': icon_char, # Updated to match asset
                    'link': url_for('main.asset_details', id=a.id),
                    'is_past': True
                })

    # 5. MAINTENANCE (Structures)
    if not filter_types or 'maintenance' in filter_types:
        for s in PropertyStructure.query.filter(PropertyStructure.date_last_maintained != None).all():
            events.append({
                'date': s.date_last_maintained,
                'title': s.name,
                'description': s.notes or "Routine maintenance logged.",
                'type': 'maintenance',
                'type_label': 'Maintenance',
                'icon': '🛠️',
                'link': url_for('main.asset_details', id=s.asset_id) + '#tab-structures',
                'is_past': True
            })

    # Sort all events by date
    events.sort(key=lambda x: x['date'])
    
    return events