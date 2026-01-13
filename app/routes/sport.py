"""
Sport Events Routes
View and manage sport events and duty assignments.
"""

from flask import Blueprint, render_template, request, jsonify, session
from datetime import date, datetime, timedelta
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

sport_bp = Blueprint('sport', __name__, url_prefix='/sport')

TENANT_ID = "MARAGON"


def get_back_url_for_user():
    """Get appropriate back URL based on user role."""
    role = session.get('role', 'teacher')
    if role in ['principal', 'deputy', 'admin']:
        return '/dashboard/', 'Dashboard'
    return '/', 'Home'


@sport_bp.route('/events')
def events():
    """View upcoming sport events."""
    today = date.today()
    
    # Get filter from query param
    filter_type = request.args.get('filter', 'upcoming')
    
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
        else:
            # All events
            cursor.execute("""
                SELECT * FROM sport_event 
                WHERE tenant_id = ? AND event_date >= ?
                ORDER BY event_date ASC, start_time ASC
            """, (TENANT_ID, today.isoformat()))
            filter_label = "All Upcoming"
        
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
