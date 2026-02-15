"""
Emergency Alert routes - Trigger, respond, resolve
"""

from flask import Blueprint, render_template, request, session, redirect, url_for, jsonify
from datetime import datetime, date, time
from app.services.db import get_connection, generate_id, now_iso
from app.services.nav import get_nav_header, get_nav_styles, get_back_url

emergency_bp = Blueprint('emergency', __name__, url_prefix='/emergency')

TENANT_ID = "MARAGON"


def get_current_user():
    """Get current user from session."""
    return {
        'staff_id': session.get('staff_id'),
        'display_name': session.get('display_name', 'Unknown'),
        'role': session.get('role', 'teacher'),
        'can_resolve': session.get('can_resolve', False),
        'default_venue_id': session.get('default_venue_id'),
        'default_venue_name': session.get('default_venue_name'),
    }




def get_smart_location(staff_id):
    """Determine teacher's current location based on time, schedule, and assignments.
    
    Returns dict with keys: venue_id, venue_name, context, or None if unknown.
    Priority: sub assignment > terrain duty > teaching slot > home room > staffroom
    """
    from datetime import datetime, date
    
    now = datetime.now()
    now_time = now.strftime('%H:%M')
    today_str = date.today().isoformat()
    today_weekday = date.today().weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
    
    # Weekend - no smart location
    if today_weekday >= 5:
        return None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get today's calendar entry
        cursor.execute("""
            SELECT cycle_day, bell_schedule FROM school_calendar
            WHERE tenant_id = ? AND date = ?
        """, (TENANT_ID, today_str))
        cal = cursor.fetchone()
        
        if not cal or not cal['cycle_day']:
            return _get_home_room(cursor, staff_id)
        
        cycle_day = cal['cycle_day']
        schedule_type = cal['bell_schedule']
        
        # Get bell schedule slots
        cursor.execute("""
            SELECT slot_name, slot_number, start_time, end_time, is_teaching, is_break, sort_order
            FROM bell_schedule
            WHERE tenant_id = ? AND schedule_type = ?
            ORDER BY sort_order
        """, (TENANT_ID, schedule_type))
        slots = [dict(row) for row in cursor.fetchall()]
        
        # Find current slot
        current_slot = None
        for slot in slots:
            if slot['start_time'] <= now_time <= slot['end_time']:
                current_slot = slot
                break
        
        # Before school (07:00-07:30) - check terrain morning duty
        if now_time < '07:30':
            terrain = _check_terrain_duty(cursor, staff_id, today_str)
            if terrain:
                return terrain
            return _get_home_room(cursor, staff_id, 'Before school')
        
        # After last slot - home room
        if not current_slot and now_time > '14:15':
            return _get_home_room(cursor, staff_id, 'After hours')
        
        # During a break - check terrain duty
        if current_slot and current_slot['is_break']:
            terrain = _check_terrain_duty(cursor, staff_id, today_str)
            if terrain:
                return terrain
            return _get_home_room(cursor, staff_id, current_slot['slot_name'])
        
        # During a teaching period
        if current_slot and current_slot['is_teaching'] and current_slot['slot_number']:
            period_num = current_slot['slot_number']
            
            # Check sub assignment first (covering someone else)
            cursor.execute("""
                SELECT sr.venue_name, p.period_number,
                       s.display_name as absent_teacher,
                       v_mg.venue_code as mentor_venue
                FROM substitute_request sr
                JOIN absence a ON sr.absence_id = a.id
                JOIN staff s ON a.staff_id = s.id
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN mentor_group mg ON mg.mentor_id = a.staff_id
                LEFT JOIN venue v_mg ON mg.venue_id = v_mg.id
                WHERE sr.substitute_id = ? AND sr.request_date = ? AND sr.status = 'Assigned'
                  AND p.period_number = ?
            """, (staff_id, today_str, period_num))
            sub = cursor.fetchone()
            if sub:
                venue_name = sub['venue_name'] or sub['mentor_venue'] or 'Unknown'
                return {
                    'venue_id': None,
                    'venue_name': venue_name,
                    'context': f'Covering for {sub["absent_teacher"]} — Period {period_num}'
                }
            
            # Check mentor duty sub (is_mentor_duty)
            cursor.execute("""
                SELECT sr.venue_name, s.display_name as absent_teacher,
                       v_mg.venue_code as mentor_venue
                FROM substitute_request sr
                JOIN absence a ON sr.absence_id = a.id
                JOIN staff s ON a.staff_id = s.id
                LEFT JOIN mentor_group mg ON mg.mentor_id = a.staff_id
                LEFT JOIN venue v_mg ON mg.venue_id = v_mg.id
                WHERE sr.substitute_id = ? AND sr.request_date = ? AND sr.status = 'Assigned'
                  AND sr.is_mentor_duty = 1
            """, (staff_id, today_str))
            mentor_sub = cursor.fetchone()
            
            # Check timetable for this period
            cursor.execute("""
                SELECT t.*, v.venue_code, v.venue_name, v.id as venue_uuid
                FROM timetable_slot t
                LEFT JOIN venue v ON t.venue_id = v.id
                WHERE t.staff_id = ? AND t.cycle_day = ?
                  AND t.period_id IN (SELECT id FROM period WHERE tenant_id = ? AND period_number = ?)
            """, (staff_id, cycle_day, TENANT_ID, period_num))
            teaching = cursor.fetchone()
            if teaching and teaching['venue_uuid']:
                return {
                    'venue_id': teaching['venue_uuid'],
                    'venue_name': teaching['venue_code'] or teaching['venue_name'],
                    'context': f'Teaching — Period {period_num}'
                }
            
            # Free period - home room
            return _get_home_room(cursor, staff_id, f'Free — Period {period_num}')
        
        # Assembly or other non-teaching slot
        if current_slot:
            return _get_home_room(cursor, staff_id, current_slot['slot_name'])
        
        # Fallback
        return _get_home_room(cursor, staff_id)


def _check_terrain_duty(cursor, staff_id, today_str):
    """Check if teacher has terrain duty today."""
    cursor.execute("""
        SELECT dr.*, ta.area_name, ta.area_code
        FROM duty_roster dr
        LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
        WHERE dr.staff_id = ? AND dr.duty_date = ? AND dr.duty_type = 'terrain'
    """, (staff_id, today_str))
    duty = cursor.fetchone()
    if duty:
        area = duty['area_name'] or duty['area_code'] or 'Terrain'
        return {
            'venue_id': duty.get('terrain_area_id'),
            'venue_name': area,
            'context': 'Terrain duty'
        }
    return None


def _get_home_room(cursor_or_none, staff_id, context=None):
    """Get teacher's home room as fallback location."""
    if cursor_or_none is None:
        return None
    cursor = cursor_or_none
    cursor.execute("""
        SELECT v.id as venue_id, v.venue_code, v.venue_name
        FROM staff_venue sv
        JOIN venue v ON sv.venue_id = v.id
        WHERE sv.staff_id = ? AND sv.tenant_id = ?
    """, (staff_id, TENANT_ID))
    room = cursor.fetchone()
    if room:
        return {
            'venue_id': room['venue_id'],
            'venue_name': room['venue_code'] or room['venue_name'],
            'context': context or 'Home room'
        }
    return None


def get_nav_for_user(user, current_page='emergency'):
    """Get navigation header and styles based on user role."""
    user_role = user.get('role', 'teacher')
    leadership_roles = ['principal', 'deputy', 'admin']
    
    if current_page in ['emergency-active', 'emergency-resolve', 'emergency-resolved']:
        if user_role in leadership_roles:
            return '/', 'Home'
        return '/', 'Home'
    elif current_page == 'history':
        return '/emergency/', 'Emergency'
    else:
        return '/', 'Home'


def get_active_alert():
    """Get currently active emergency alert if any."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ea.*, s.display_name as triggered_by_name
            FROM emergency_alert ea
            LEFT JOIN staff s ON ea.triggered_by_id = s.id
            WHERE ea.tenant_id = ? AND ea.status = 'Active'
            ORDER BY ea.triggered_at DESC
            LIMIT 1
        """, (TENANT_ID,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_response_count(alert_id):
    """Get number of responders for an alert."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as count FROM emergency_response WHERE alert_id = ?
        """, (alert_id,))
        return cursor.fetchone()['count']


def get_responders(alert_id):
    """Get list of responders for an alert."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT er.*, s.display_name as responder_name
            FROM emergency_response er
            LEFT JOIN staff s ON er.responder_id = s.id
            WHERE er.alert_id = ?
            ORDER BY er.responded_at ASC
        """, (alert_id,))
        return [dict(row) for row in cursor.fetchall()]


def has_responded(alert_id, staff_id):
    """Check if staff member has already responded."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM emergency_response WHERE alert_id = ? AND responder_id = ?
        """, (alert_id, staff_id))
        return cursor.fetchone() is not None


def can_user_resolve(user, alert):
    """Check if user can resolve this alert - any logged in staff member."""
    if not user.get('staff_id') or not alert:
        return False
    return True


@emergency_bp.route('/')
def index():
    """Emergency home - show trigger button or active alert."""
    user = get_current_user()
    if not user['staff_id']:
        return redirect('/?error=not_logged_in')
    
    active_alert = get_active_alert()
    nav_styles = get_nav_styles()
    
    if active_alert:
        responders = get_responders(active_alert['id'])
        user_responded = has_responded(active_alert['id'], user['staff_id'])
        
        triggered_dt = datetime.fromisoformat(active_alert['triggered_at'])
        elapsed = datetime.now() - triggered_dt
        elapsed_str = f"{int(elapsed.total_seconds() // 60)}m {int(elapsed.total_seconds() % 60)}s"
        
        user_can_resolve = can_user_resolve(user, active_alert)
        
        back_url, back_label = get_nav_for_user(user, 'emergency-active')
        nav_header = get_nav_header('🚨 ACTIVE ALERT', back_url, back_label)
        
        return render_template('emergency/active.html',
                             user=user,
                             alert=active_alert,
                             responders=responders,
                             response_count=len(responders),
                             user_responded=user_responded,
                             user_can_resolve=user_can_resolve,
                             elapsed=elapsed_str,
                             nav_header=nav_header,
                             nav_styles=nav_styles)
    
    nav_header = get_nav_header('Emergency', '/', 'Home')
    return render_template('emergency/trigger.html', 
                         user=user,
                         nav_header=nav_header,
                         nav_styles=nav_styles)


@emergency_bp.route('/trigger', methods=['GET', 'POST'])
def trigger():
    """Trigger new emergency - select type and location."""
    user = get_current_user()
    if not user['staff_id']:
        return redirect('/?error=not_logged_in')
    
    if get_active_alert():
        return redirect(url_for('emergency.index'))
    
    if request.method == 'GET':
        nav_header = get_nav_header('Select Type', '/emergency/', 'Cancel')
        nav_styles = get_nav_styles()
        return render_template('emergency/select_type.html', 
                             user=user,
                             nav_header=nav_header,
                             nav_styles=nav_styles)
    
    alert_type = request.form.get('alert_type')
    if alert_type not in ('Medical', 'Security', 'Fire', 'General'):
        return redirect(url_for('emergency.trigger'))
    
    session['pending_alert_type'] = alert_type
    return redirect(url_for('emergency.select_location'))


@emergency_bp.route('/select-location')
def select_location():
    """Select location for emergency - two-step: zone then venue."""
    user = get_current_user()
    alert_type = session.get('pending_alert_type')
    
    if not alert_type:
        return redirect(url_for('emergency.trigger'))
    
    zones = [
        ('Bathroom', 'Bathroom'),
        ('A_Ground', 'A Block Ground'),
        ('A_First', 'A Block First Floor'),
        ('A_Admin', 'A Block Admin/IT'),
        ('B_Block', 'B Block'),
        ('C_Block', 'C Block'),
        ('D_Block', 'D Block'),
        ('Outdoor', 'Outdoor Areas'),
        ('Admin', 'Admin Offices'),
    ]
    
    nav_header = get_nav_header('Select Location', '/emergency/trigger', 'Back')
    nav_styles = get_nav_styles()
    
    # Smart location: figure out where teacher actually is right now
    smart = get_smart_location(user['staff_id'])
    if smart:
        quick_venue_id = smart['venue_id'] or user.get('default_venue_id')
        quick_venue_name = smart['venue_name']
        quick_context = smart.get('context', '')
    else:
        quick_venue_id = user.get('default_venue_id')
        quick_venue_name = user.get('default_venue_name')
        quick_context = 'Home room' if quick_venue_name else ''
    
    return render_template('emergency/select_zone.html',
                         user=user,
                         alert_type=alert_type,
                         zones=zones,
                         default_venue_id=quick_venue_id,
                         default_venue_name=quick_venue_name,
                         default_venue_context=quick_context,
                         nav_header=nav_header,
                         nav_styles=nav_styles)


@emergency_bp.route('/send-default', methods=['POST'])
def send_default():
    """Quick-send alert using user's default location."""
    user = get_current_user()
    alert_type = session.get('pending_alert_type')
    
    if not alert_type or not user['staff_id']:
        return redirect(url_for('emergency.index'))
    
    # Accept smart location from form, fall back to session default
    default_venue_id = request.form.get('venue_id') or user.get('default_venue_id')
    default_venue_name = request.form.get('venue_name') or user.get('default_venue_name')
    
    if not default_venue_id and not default_venue_name:
        return redirect(url_for('emergency.select_location'))
    
    # If we have a name but no UUID (e.g. terrain area), use name as ID
    if not default_venue_id:
        default_venue_id = default_venue_name
    
    with get_connection() as conn:
        cursor = conn.cursor()
        alert_id = generate_id()
        cursor.execute("""
            INSERT INTO emergency_alert 
            (id, tenant_id, alert_type, venue_id, location_display, triggered_by_id, triggered_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (alert_id, TENANT_ID, alert_type, default_venue_id, default_venue_name, user['staff_id'], now_iso()))
        conn.commit()
    
    session.pop('pending_alert_type', None)
    
    try:
        from app.routes.push import send_emergency_alert_push
        send_emergency_alert_push(alert_type, default_venue_name, user['display_name'])
    except Exception as e:
        print(f"Push notification error: {e}")
    
    return redirect(url_for('emergency.index'))


@emergency_bp.route('/venues/<block>')
def get_venues_by_block(block):
    """HTMX endpoint - get venues for a block."""
    user = get_current_user()
    
    if block == 'Bathroom':
        bathrooms = [
            {'id': 'BG_BOYS_A001', 'venue_code': 'BG_BOYS', 'venue_name': 'Boys - Ground - Near A001'},
            {'id': 'BG_GIRLS_A006', 'venue_code': 'BG_GIRLS', 'venue_name': 'Girls - Ground - Near A006'},
            {'id': 'BG_GIRLS_A008', 'venue_code': 'BG_GIRLS', 'venue_name': 'Girls - Ground - Near A008'},
            {'id': 'BG_GIRLS_KITCHEN', 'venue_code': 'BG_GIRLS', 'venue_name': 'Girls - Ground - Near Kitchen'},
            {'id': 'B1_BOYS_A101', 'venue_code': 'B1_BOYS', 'venue_name': 'Boys - 1st Floor - Near A101'},
            {'id': 'B1_GIRLS_A105', 'venue_code': 'B1_GIRLS', 'venue_name': 'Girls - 1st Floor - Near A105'},
            {'id': 'B1_GIRLS_A107', 'venue_code': 'B1_GIRLS', 'venue_name': 'Girls - 1st Floor - Near A107'},
            {'id': 'B1_GIRLS_A112', 'venue_code': 'B1_GIRLS', 'venue_name': 'Girls - 1st Floor - Near A112'},
        ]
        return render_template('emergency/partials/venue_list.html',
                             venues=bathrooms,
                             default_venue_id=user.get('default_venue_id'),
                             is_bathroom=True)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, venue_code, venue_name FROM venue
            WHERE tenant_id = ? AND block = ? AND is_active = 1
            ORDER BY sort_order
        """, (TENANT_ID, block))
        venues = [dict(row) for row in cursor.fetchall()]
    
    return render_template('emergency/partials/venue_list.html',
                         venues=venues,
                         default_venue_id=user.get('default_venue_id'),
                         is_bathroom=False)


@emergency_bp.route('/send', methods=['POST'])
def send_alert():
    """Send the emergency alert."""
    user = get_current_user()
    alert_type = session.get('pending_alert_type')
    venue_id = request.form.get('venue_id')
    
    if not alert_type or not venue_id or not user['staff_id']:
        return redirect(url_for('emergency.index'))
    
    if venue_id.startswith('BG_') or venue_id.startswith('B1_'):
        bathroom_names = {
            'BG_BOYS_A001': 'Bathroom - Boys - Ground - Near A001',
            'BG_GIRLS_A006': 'Bathroom - Girls - Ground - Near A006',
            'BG_GIRLS_A008': 'Bathroom - Girls - Ground - Near A008',
            'BG_GIRLS_KITCHEN': 'Bathroom - Girls - Ground - Near Kitchen',
            'B1_BOYS_A101': 'Bathroom - Boys - 1st Floor - Near A101',
            'B1_GIRLS_A105': 'Bathroom - Girls - 1st Floor - Near A105',
            'B1_GIRLS_A107': 'Bathroom - Girls - 1st Floor - Near A107',
            'B1_GIRLS_A112': 'Bathroom - Girls - 1st Floor - Near A112',
        }
        location_display = bathroom_names.get(venue_id, 'Bathroom - Unknown')
    else:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT venue_name FROM venue WHERE id = ?", (venue_id,))
            venue_row = cursor.fetchone()
            location_display = venue_row['venue_name'] if venue_row else 'Unknown'
    
    with get_connection() as conn:
        cursor = conn.cursor()
        alert_id = generate_id()
        cursor.execute("""
            INSERT INTO emergency_alert 
            (id, tenant_id, alert_type, venue_id, location_display, triggered_by_id, triggered_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (alert_id, TENANT_ID, alert_type, venue_id, location_display, user['staff_id'], now_iso()))
        conn.commit()
    
    session.pop('pending_alert_type', None)
    
    try:
        from app.routes.push import send_emergency_alert_push
        send_emergency_alert_push(alert_type, location_display, user['display_name'])
    except Exception as e:
        print(f"Push notification error: {e}")
    
    return redirect(url_for('emergency.index'))


@emergency_bp.route('/respond', methods=['POST'])
def respond():
    """Mark current user as responding."""
    user = get_current_user()
    active_alert = get_active_alert()
    
    if not active_alert or not user['staff_id']:
        return redirect(url_for('emergency.index'))
    
    if has_responded(active_alert['id'], user['staff_id']):
        return redirect(url_for('emergency.index'))
    
    with get_connection() as conn:
        cursor = conn.cursor()
        response_id = generate_id()
        cursor.execute("""
            INSERT INTO emergency_response (id, alert_id, responder_id, responded_at)
            VALUES (?, ?, ?, ?)
        """, (response_id, active_alert['id'], user['staff_id'], now_iso()))
        conn.commit()
    
    return redirect(url_for('emergency.index'))


@emergency_bp.route('/resolve', methods=['GET', 'POST'])
def resolve():
    """Resolve the active alert."""
    user = get_current_user()
    active_alert = get_active_alert()
    
    if not active_alert:
        return redirect(url_for('emergency.index'))
    
    if not can_user_resolve(user, active_alert):
        return redirect(url_for('emergency.index'))
    
    if request.method == 'GET':
        responders = get_responders(active_alert['id'])
        nav_header = get_nav_header('Resolve Alert', '/emergency/', 'Back')
        nav_styles = get_nav_styles()
        return render_template('emergency/resolve.html',
                             user=user,
                             alert=active_alert,
                             responders=responders,
                             nav_header=nav_header,
                             nav_styles=nav_styles)
    
    resolution_type = request.form.get('resolution_type', 'AllClear')
    resolution_notes = request.form.get('notes', '')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE emergency_alert
            SET status = 'Resolved', resolved_at = ?, resolved_by_id = ?,
                resolution_type = ?, resolution_notes = ?
            WHERE id = ?
        """, (now_iso(), user['staff_id'], resolution_type, resolution_notes, active_alert['id']))
        conn.commit()
    
    try:
        from app.routes.push import send_all_clear_push
        send_all_clear_push(active_alert['alert_type'], active_alert['location_display'], user['display_name'])
    except Exception as e:
        print(f"All Clear push error: {e}")
    
    return redirect(url_for('emergency.resolved'))


@emergency_bp.route('/resolved')
def resolved():
    """Show resolution confirmation."""
    user = get_current_user()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ea.*, s.display_name as resolved_by_name
            FROM emergency_alert ea
            LEFT JOIN staff s ON ea.resolved_by_id = s.id
            WHERE ea.tenant_id = ? AND ea.status = 'Resolved'
            ORDER BY ea.resolved_at DESC
            LIMIT 1
        """, (TENANT_ID,))
        row = cursor.fetchone()
        alert = dict(row) if row else None
    
    back_url, back_label = get_nav_for_user(user, 'emergency-resolved')
    nav_header = get_nav_header('All Clear', back_url, back_label)
    nav_styles = get_nav_styles()
    
    return render_template('emergency/resolved.html', 
                         user=user, 
                         alert=alert,
                         nav_header=nav_header,
                         nav_styles=nav_styles)


@emergency_bp.route('/banner')
def banner():
    """HTMX endpoint - returns alert banner if active."""
    active_alert = get_active_alert()
    user = get_current_user()
    
    if not active_alert:
        return ''
    
    response_count = get_response_count(active_alert['id'])
    user_responded = has_responded(active_alert['id'], user.get('staff_id')) if user.get('staff_id') else False
    
    triggered_dt = datetime.fromisoformat(active_alert['triggered_at'])
    elapsed = datetime.now() - triggered_dt
    elapsed_str = f"{int(elapsed.total_seconds() // 60)}m {int(elapsed.total_seconds() % 60)}s"
    
    return render_template('emergency/partials/banner.html',
                         alert=active_alert,
                         response_count=response_count,
                         user_responded=user_responded,
                         elapsed=elapsed_str,
                         user=user)


@emergency_bp.route('/responders/<alert_id>')
def responders_partial(alert_id):
    """HTMX endpoint - returns updated responder list."""
    responders = get_responders(alert_id)
    return render_template('emergency/partials/responders.html', responders=responders)


@emergency_bp.route('/status')
def status():
    """API endpoint - returns current alert status as JSON."""
    active_alert = get_active_alert()
    
    if not active_alert:
        return jsonify({'active': False})
    
    return jsonify({
        'active': True,
        'id': active_alert['id'],
        'type': active_alert['alert_type'],
        'location': active_alert['location_display'],
        'triggered_by': active_alert.get('triggered_by_name', 'Unknown'),
        'response_count': get_response_count(active_alert['id']),
    })


@emergency_bp.route('/check/<alert_id>')
def check_alert(alert_id):
    """Check if specific alert is still active."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM emergency_alert WHERE id = ?', (alert_id,))
        alert = cursor.fetchone()
    
    if not alert or alert['status'] != 'Active':
        return '<script>window.location.href="/emergency/resolved";</script>'
    
    return ''


@emergency_bp.route('/history')
def history():
    """View alert history with date filtering."""
    user = get_current_user()
    if not user['staff_id']:
        return redirect('/?error=not_logged_in')
    
    from datetime import date
    
    today = date.today().isoformat()
    date_from = request.args.get('from', today)
    date_to = request.args.get('to', today)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                ea.*,
                triggered.display_name as triggered_by_name,
                resolved.display_name as resolved_by_name
            FROM emergency_alert ea
            LEFT JOIN staff triggered ON ea.triggered_by_id = triggered.id
            LEFT JOIN staff resolved ON ea.resolved_by_id = resolved.id
            WHERE ea.tenant_id = ?
              AND date(ea.triggered_at) >= ?
              AND date(ea.triggered_at) <= ?
            ORDER BY ea.triggered_at DESC
        """, (TENANT_ID, date_from, date_to))
        
        alerts = []
        for row in cursor.fetchall():
            alert = dict(row)
            
            cursor.execute("""
                SELECT s.display_name 
                FROM emergency_response er
                JOIN staff s ON er.responder_id = s.id
                WHERE er.alert_id = ?
                ORDER BY er.responded_at ASC
            """, (alert['id'],))
            responders = [r['display_name'] for r in cursor.fetchall()]
            alert['responder_count'] = len(responders)
            alert['responder_names'] = ', '.join(responders) if responders else 'None'
            
            if alert['resolved_at'] and alert['triggered_at']:
                triggered = datetime.fromisoformat(alert['triggered_at'])
                resolved = datetime.fromisoformat(alert['resolved_at'])
                duration = resolved - triggered
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                alert['duration'] = f"{minutes}m {seconds}s"
            else:
                alert['duration'] = 'Active' if alert['status'] == 'Active' else 'Unknown'
            
            triggered_dt = datetime.fromisoformat(alert['triggered_at'])
            alert['triggered_time'] = triggered_dt.strftime('%H:%M')
            alert['triggered_date'] = triggered_dt.strftime('%d %b')
            
            alerts.append(alert)
    
    nav_header = get_nav_header('Alert History', '/emergency/', 'Emergency')
    nav_styles = get_nav_styles()
    
    return render_template('emergency/history.html',
                         user=user,
                         alerts=alerts,
                         date_from=date_from,
                         date_to=date_to,
                         nav_header=nav_header,
                         nav_styles=nav_styles)


@emergency_bp.route('/responders-section/<alert_id>')
def responders_section(alert_id):
    """HTMX endpoint - returns responders section with count."""
    responders = get_responders(alert_id)
    count = len(responders)
    
    html = f'''
    <div class="responders-title">
        <span>Responders</span>
        <span class="responders-count">{count}</span>
    </div>
    <div class="responder-list">
    '''
    
    if responders:
        for r in responders:
            html += f'<div class="responder-item"><span>✓ {r["responder_name"]}</span></div>'
    else:
        html += '<div class="no-responders">No responders yet</div>'
    
    html += '</div>'
    return html
