"""
Sport Events Routes
View and manage sport events and duty assignments.
"""

from flask import Blueprint, render_template, request, jsonify, session, redirect
from datetime import date, datetime, timedelta
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

sport_bp = Blueprint('sport', __name__, url_prefix='/sport')

TENANT_ID = "MARAGON"

# Duty types by sport
DUTY_TYPES = {
    'common': ['Supervision', 'First Aid', 'Transport', 'Refreshments'],
    'Athletics': ['Announcer', 'Timekeeper', 'Starter', 'Results', 'Field Judge', 'Track Judge'],
    'Swimming': ['Announcer', 'Timekeeper', 'Starter', 'Lane Judge', 'Results'],
    'Rugby': ['Team Manager', 'Scorer'],
    'Hockey': ['Team Manager', 'Scorer'],
    'Soccer': ['Team Manager', 'Scorer'],
    'Netball': ['Team Manager', 'Scorer'],
    'Softball': ['Team Manager', 'Scorer'],
    'Cricket': ['Team Manager', 'Scorer', 'Umpire'],
    'Tennis': ['Umpire', 'Scorer'],
    'Cross-Country': ['Marshal', 'Water Station', 'Results'],
    'Multi-Sport': ['Announcer', 'Results'],
    'Quiz': ['Quiz Master', 'Scorer'],
}


def get_duty_types_for_sport(sport_type):
    """Get duty types for a specific sport (common + sport-specific + Other)."""
    types = DUTY_TYPES['common'].copy()
    if sport_type in DUTY_TYPES:
        types.extend(DUTY_TYPES[sport_type])
    types.append('Other')
    return types


def get_back_url_for_user():
    """Get appropriate back URL based on user role."""
    return '/', 'Home'


@sport_bp.route('/events')
def events():
    """View upcoming sport events."""
    today = date.today()
    
    # Get filter from query param
    filter_type = request.args.get('filter', 'this_week')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if filter_type == 'upcoming':
            # Next 30 days
            end_date = today + timedelta(days=30)
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ? AND event_date >= ? AND event_date <= ?
                ORDER BY event_date ASC, start_time ASC
            """, (TENANT_ID, today.isoformat(), end_date.isoformat()))
            filter_label = "Next 30 Days"
        elif filter_type == 'this_week':
            # This week (Mon-Sun)
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ? AND event_date >= ? AND event_date <= ?
                ORDER BY event_date ASC, start_time ASC
            """, (TENANT_ID, start_of_week.isoformat(), end_of_week.isoformat()))
            filter_label = "This Week"
        elif filter_type == 'this_month':
            # This month
            start_of_month = today.replace(day=1)
            if today.month == 12:
                end_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ? AND event_date >= ? AND event_date <= ?
                ORDER BY event_date ASC, start_time ASC
            """, (TENANT_ID, start_of_month.isoformat(), end_of_month.isoformat()))
            filter_label = today.strftime("%B %Y")
        elif filter_type == 'past':
            # Past 30 days
            start_date = today - timedelta(days=30)
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ? AND event_date < ? AND event_date >= ?
                ORDER BY event_date DESC, start_time ASC
            """, (TENANT_ID, today.isoformat(), start_date.isoformat()))
            filter_label = "Past 30 Days"
        else:
            # All events (past + future)
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ?
                ORDER BY event_date ASC, start_time ASC
            """, (TENANT_ID,))
            filter_label = "All Events"
        
        events_raw = cursor.fetchall()
        
        # Group events by date
        events_by_date = {}
        for row in events_raw:
            event = dict(row)
            event_date = event['event_date']
            
            # Parse date for display
            dt = datetime.strptime(event_date, '%Y-%m-%d')
            event['day_name'] = dt.strftime('%A')
            event['date_display'] = dt.strftime('%d %b')
            event['is_today'] = event_date == today.isoformat()
            event['is_tomorrow'] = event_date == (today + timedelta(days=1)).isoformat()
            
            # Format times
            if event['start_time'] and event['end_time']:
                event['time_display'] = f"{event['start_time']} - {event['end_time']}"
            elif event['start_time']:
                event['time_display'] = event['start_time']
            else:
                event['time_display'] = "TBC"
            
            if event_date not in events_by_date:
                events_by_date[event_date] = {
                    'date': event_date,
                    'day_name': event['day_name'],
                    'date_display': event['date_display'],
                    'is_today': event['is_today'],
                    'is_tomorrow': event['is_tomorrow'],
                    'events': []
                }
            events_by_date[event_date]['events'].append(event)
        
        # Convert to sorted list
        grouped_events = sorted(events_by_date.values(), key=lambda x: x['date'])
        total_events = len(events_raw)
    
    back_url, back_label = get_back_url_for_user()
    nav_header = get_nav_header("Sport Events", back_url, back_label)
    nav_styles = get_nav_styles()
    
    return render_template('sport/events.html',
                          grouped_events=grouped_events,
                          total_events=total_events,
                          filter_type=filter_type,
                          filter_label=filter_label,
                          today=today.isoformat(),
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@sport_bp.route('/event/<event_id>')
def event_detail(event_id):
    """View single event with duty assignments."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get event
        cursor.execute("""
            SELECT * FROM sport_event WHERE id = ? AND tenant_id = ?
        """, (event_id, TENANT_ID))
        row = cursor.fetchone()
        
        if not row:
            return "Event not found", 404
        
        event = dict(row)
        
        # Parse date for display
        dt = datetime.strptime(event['event_date'], '%Y-%m-%d')
        event['day_name'] = dt.strftime('%A')
        event['date_display'] = dt.strftime('%d %B %Y')
        
        # Format times
        if event['start_time'] and event['end_time']:
            event['time_display'] = f"{event['start_time']} - {event['end_time']}"
        elif event['start_time']:
            event['time_display'] = f"From {event['start_time']}"
        else:
            event['time_display'] = "Time TBC"
        
        # Get duty assignments
        cursor.execute("""
            SELECT sd.*, s.display_name, s.first_name
            FROM sport_duty sd
            JOIN staff s ON sd.staff_id = s.id
            WHERE sd.event_id = ? AND sd.tenant_id = ?
            ORDER BY sd.duty_type, s.surname
        """, (event_id, TENANT_ID))
        
        duties_raw = cursor.fetchall()
        
        # Group duties by type
        duties_by_type = {}
        for row in duties_raw:
            duty = dict(row)
            duty_type = duty['duty_type']
            if duty_type not in duties_by_type:
                duties_by_type[duty_type] = []
            duties_by_type[duty_type].append(duty)
        
        duties = [{'type': k, 'staff': v} for k, v in sorted(duties_by_type.items())]
    
    nav_header = get_nav_header(event['event_name'], '/sport/events', 'Events')
    nav_styles = get_nav_styles()
    
    return render_template('sport/event_detail.html',
                          event=event,
                          duties=duties,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@sport_bp.route('/my-duties')
def my_duties():
    """View current user's sport duty assignments."""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return "Please log in to view your duties", 401
    
    today = date.today()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get upcoming duties for this staff member
        cursor.execute("""
            SELECT sd.*, se.event_name, se.event_date, se.start_time, se.end_time,
                   se.sport_type, se.location_type, se.venue_name
            FROM sport_duty sd
            JOIN sport_event se ON sd.event_id = se.id
            WHERE sd.staff_id = ? AND sd.tenant_id = ? AND se.event_date >= ?
            ORDER BY se.event_date ASC, se.start_time ASC
        """, (staff_id, TENANT_ID, today.isoformat()))
        
        duties_raw = cursor.fetchall()
        duties = []
        
        for row in duties_raw:
            duty = dict(row)
            dt = datetime.strptime(duty['event_date'], '%Y-%m-%d')
            duty['day_name'] = dt.strftime('%A')
            duty['date_display'] = dt.strftime('%d %b')
            duty['is_today'] = duty['event_date'] == today.isoformat()
            duty['is_tomorrow'] = duty['event_date'] == (today + timedelta(days=1)).isoformat()
            
            if duty['start_time'] and duty['end_time']:
                duty['time_display'] = f"{duty['start_time']} - {duty['end_time']}"
            else:
                duty['time_display'] = duty['start_time'] or "TBC"
            
            duties.append(duty)
    
    nav_header = get_nav_header("My Sport Duties", '/', 'Home')
    nav_styles = get_nav_styles()
    
    return render_template('sport/my_duties.html',
                          duties=duties,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


# ============================================================
# SPORTS COORDINATION ROUTES
# ============================================================

@sport_bp.route('/coordination')
def coordination():
    """Sports Coordination home - manage events and assign duties."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    today = date.today()
    view = request.args.get('view', 'my')  # 'my' or 'all'
    sport_filter = request.args.get('sport', '')  # filter by sport type
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Build query based on view
        if view == 'my':
            query = """
                SELECT se.*, c.display_name as coordinator_name,
                       (SELECT COUNT(*) FROM sport_duty sd WHERE sd.event_id = se.id) as duty_count
                FROM sport_event se
                LEFT JOIN staff c ON se.coordinator_id = c.id
                WHERE se.tenant_id = ? AND se.event_date >= ? AND se.coordinator_id = ?
            """
            params = [TENANT_ID, today.isoformat(), staff_id]
        else:
            query = """
                SELECT se.*, c.display_name as coordinator_name,
                       (SELECT COUNT(*) FROM sport_duty sd WHERE sd.event_id = se.id) as duty_count
                FROM sport_event se
                LEFT JOIN staff c ON se.coordinator_id = c.id
                WHERE se.tenant_id = ? AND se.event_date >= ?
            """
            params = [TENANT_ID, today.isoformat()]
        
        if sport_filter:
            query += " AND se.sport_type = ?"
            params.append(sport_filter)
        
        query += " ORDER BY se.event_date ASC, se.start_time ASC"
        cursor.execute(query, params)
        events_raw = cursor.fetchall()
        
        events = []
        for row in events_raw:
            event = dict(row)
            dt = datetime.strptime(event['event_date'], '%Y-%m-%d')
            event['day_name'] = dt.strftime('%A')
            event['date_display'] = dt.strftime('%a %d %b')
            event['is_mine'] = event.get('coordinator_id') == staff_id
            event['is_unclaimed'] = event.get('coordinator_id') is None
            events.append(event)
        
        # Get unique sport types for filter
        cursor.execute("""
            SELECT DISTINCT sport_type FROM sport_event 
            WHERE tenant_id = ? ORDER BY sport_type
        """, (TENANT_ID,))
        sport_types = [row['sport_type'] for row in cursor.fetchall()]
        
        # Count stats
        my_count = sum(1 for e in events if e['is_mine']) if view == 'all' else len(events)
        unclaimed_count = sum(1 for e in events if e['is_unclaimed'])
    
    nav_header = get_nav_header("Sports Coordination", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('sport/coordination.html',
                          events=events,
                          view=view,
                          sport_filter=sport_filter,
                          sport_types=sport_types,
                          my_count=my_count,
                          unclaimed_count=unclaimed_count,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@sport_bp.route('/coordination/claim/<event_id>', methods=['POST'])
def claim_event(event_id):
    """Take ownership of an event."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE sport_event SET coordinator_id = ? WHERE id = ? AND tenant_id = ?
        """, (staff_id, event_id, TENANT_ID))
        conn.commit()
    
    return redirect(request.referrer or '/sport/coordination')


@sport_bp.route('/coordination/release/<event_id>', methods=['POST'])
def release_event(event_id):
    """Release ownership of an event."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Only release if current user owns it
        cursor.execute("""
            UPDATE sport_event SET coordinator_id = NULL 
            WHERE id = ? AND tenant_id = ? AND coordinator_id = ?
        """, (event_id, TENANT_ID, staff_id))
        conn.commit()
    
    return redirect(request.referrer or '/sport/coordination')
