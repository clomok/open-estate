from datetime import date, datetime
from flask import url_for
from src.models import Event, RecurringBill, Holding, PropertyStructure
from src.money import format_cents

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
    
    # 1. EVENTS (what used to be milestones and tasks)
    if not filter_types or 'milestone' in filter_types or 'task' in filter_types:
        for e in Event.query.filter(Event.date != None).all():
            etype = 'milestone' if e.kind == 'milestone' else 'task'
            if filter_types and etype not in filter_types:
                continue
            events.append({
                'date': e.date,
                'title': e.title,
                'description': e.description,
                'type': etype,
                'type_label': e.kind_label,
                'icon': e.icon,
                'link': url_for('main.holding_details', id=e.holding_id) if e.holding_id else '#',
                'is_past': e.date < today
            })

    # 2. RECURRING BILLS (Next Due Date)
    if not filter_types or 'financial' in filter_types:
        for b in RecurringBill.query.filter(RecurringBill.next_due_date != None).all():
            events.append({
                'date': b.next_due_date,
                'title': b.name,
                'description': f"Payee: {b.payee} (~{format_cents(b.amount_cents)})",
                'type': 'financial',
                'type_label': 'Bill Due',
                'icon': '💳',
                'link': url_for('main.holding_details', id=b.holding_id) + '#tab-bills',
                'is_past': b.next_due_date < today
            })

    # 4. ASSET HISTORY (Purchases & Appraisals)
    if not filter_types or 'history' in filter_types:
        for a in Holding.query.all():
            icon_char = a.icon

            # A. Purchase Date (from attributes)
            p_date_str = (a.attributes or {}).get('purchase_date')
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
                        'link': url_for('main.holding_details', id=a.id),
                        'is_past': True
                    })
                except ValueError:
                    pass
            
            # B. Appraisals (History)
            for app in a.valuations:
                events.append({
                    'date': app.date,
                    'title': a.name,
                    'description': f"Valued at {format_cents(app.value_cents)} ({app.source})",
                    'type': 'history',
                    'type_label': 'Appraisal',
                    'icon': icon_char, # Updated to match asset
                    'link': url_for('main.holding_details', id=a.id),
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
                'link': url_for('main.holding_details', id=s.holding_id) + '#tab-structures',
                'is_past': True
            })

    # Sort all events by date
    events.sort(key=lambda x: x['date'])
    
    return events