"""
Substitute routes - Report absence, view assignments, Mission Control
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from datetime import date, datetime, timedelta
import uuid
from app.services.db import get_connection, create_absence_multiday
from app.services.substitute_engine import (
    create_absence, process_absence, get_cycle_day,
    get_teacher_schedule, get_current_pointer
)
from app.services.nav import get_nav_header, get_nav_styles

substitute_bp = Blueprint('substitute', __name__, url_prefix='/substitute')

TENANT_ID = "MARAGON"


def get_back_url_for_user():
    """Get appropriate back URL based on user role."""
    role = session.get('role', 'teacher')
    if role in ['principal', 'deputy', 'admin']:
        return '/dashboard/', 'Dashboard'
    return '/', 'Home'


@substitute_bp.route('/')
def index():
    """Substitute home - links to report absence or view assignments."""
    staff_id = session.get('staff_id')
    display_name = session.get('display_name', 'Teacher')
    back_url, back_label = get_back_url_for_user()
    nav_header = get_nav_header("Substitutes", back_url, back_label)
    nav_styles = get_nav_styles()
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Substitutes - SchoolOps</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; padding: 20px; color: white; }}
        .container {{ max-width: 500px; margin: 0 auto; }}
        {nav_styles}
        .menu {{ display: flex; flex-direction: column; gap: 16px; margin-top: 20px; }}
        .menu-item {{ display: block; padding: 20px; background: rgba(255,255,255,0.1); border-radius: 12px; text-decoration: none; color: white; }}
        .menu-item:hover {{ background: rgba(255,255,255,0.15); }}
        .menu-item h3 {{ font-size: 18px; margin-bottom: 4px; }}
        .menu-item p {{ font-size: 14px; opacity: 0.7; }}
        .menu-icon {{ font-size: 24px; margin-bottom: 8px; }}
    </style>
</head>
<body>
    <div class="container">
        {nav_header}
        <div class="menu">
            <a href="/substitute/report" class="menu-item">
                <div class="menu-icon">🤒</div>
                <h3>Report Absence</h3>
                <p>I'm sick and need cover today</p>
            </a>
            <a href="/substitute/my-assignments" class="menu-item">
                <div class="menu-icon">📋</div>
                <h3>My Assignments</h3>
                <p>View my substitute duties</p>
            </a>
            {f'<a href="/substitute/mission-control" class="menu-item"><div class="menu-icon">🎛️</div><h3>Mission Control</h3><p>Manage all absences and coverage</p></a>' if session.get('role') in ['principal', 'deputy', 'admin'] else ''}
        </div>
    </div>
</body>
</html>
'''


@substitute_bp.route('/report', methods=['GET', 'POST'])
def report_absence():
    """Teacher reports their own absence (supports multi-day)."""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return redirect('/?u=beatrix')
    
    if request.method == 'GET':
        # Check for active absence (for early return option)
        active_absence = None
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Find active absence for this teacher
            cursor.execute("""
                SELECT id, absence_date, end_date, is_open_ended, absence_type, status
                FROM absence 
                WHERE staff_id = ? AND tenant_id = ? 
                AND status IN ('Reported', 'Covered', 'Partial')
                AND (
                    (end_date IS NULL AND absence_date >= ?)
                    OR (end_date IS NOT NULL AND end_date >= ?)
                    OR is_open_ended = 1
                )
                ORDER BY absence_date DESC
                LIMIT 1
            """, (staff_id, TENANT_ID, date.today().isoformat(), date.today().isoformat()))
            row = cursor.fetchone()
            
            if row:
                active_absence = dict(row)
                # Format dates for display
                try:
                    start_dt = datetime.strptime(active_absence['absence_date'], '%Y-%m-%d')
                    active_absence['start_display'] = start_dt.strftime('%a %d %b')
                    if active_absence['end_date']:
                        end_dt = datetime.strptime(active_absence['end_date'], '%Y-%m-%d')
                        active_absence['end_display'] = end_dt.strftime('%a %d %b')
                except:
                    active_absence['start_display'] = active_absence['absence_date']
                    active_absence['end_display'] = active_absence.get('end_date', '')
            
            # Get periods for partial day option
            cursor.execute("""
                SELECT id, period_number, period_name, start_time, end_time
                FROM period 
                WHERE tenant_id = ? AND is_teaching = 1
                ORDER BY sort_order
            """, (TENANT_ID,))
            periods = [dict(row) for row in cursor.fetchall()]
        
        return render_template('substitute/report.html',
                              periods=periods,
                              today=date.today().isoformat(),
                              active_absence=active_absence)
    
    # POST: Create new absence
    absence_type = request.form.get('absence_type', 'Sick')
    reason = request.form.get('reason', '')
    start_date = request.form.get('start_date', date.today().isoformat())
    end_date = request.form.get('end_date', start_date)
    is_open_ended = request.form.get('is_open_ended') == '1'
    is_full_day = request.form.get('is_full_day', '1') == '1'
    
    # If open-ended, clear end_date
    if is_open_ended:
        end_date = None
    
    absence_id = create_absence_multiday(
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
        is_open_ended=is_open_ended,
        absence_type=absence_type,
        reason=reason,
        is_full_day=is_full_day
    )
    
    results = process_absence(absence_id)
    
    return redirect(url_for('substitute.absence_status', absence_id=absence_id))


@substitute_bp.route('/early-return', methods=['POST'])
def early_return():
    """Teacher reports early return - cancels remaining substitute assignments."""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return redirect('/')
    
    absence_id = request.form.get('absence_id')
    return_date = request.form.get('return_date', date.today().isoformat())
    
    if not absence_id:
        return redirect(url_for('substitute.report_absence'))
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verify this absence belongs to the teacher
        cursor.execute("""
            SELECT id, absence_date, end_date FROM absence 
            WHERE id = ? AND staff_id = ?
        """, (absence_id, staff_id))
        absence = cursor.fetchone()
        
        if not absence:
            return redirect(url_for('substitute.report_absence'))
        
        # Update absence record
        cursor.execute("""
            UPDATE absence 
            SET returned_early = 1, 
                returned_at = ?,
                return_reported_by_id = ?,
                end_date = ?,
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), staff_id, return_date, datetime.now().isoformat(), absence_id))
        
        # Cancel all substitute requests from return_date onwards
        cursor.execute("""
            UPDATE substitute_request
            SET status = 'Cancelled',
                cancelled_at = ?,
                cancel_reason = 'early_return',
                updated_at = ?
            WHERE absence_id = ? 
            AND request_date >= ?
            AND status IN ('Pending', 'Assigned')
        """, (datetime.now().isoformat(), datetime.now().isoformat(), absence_id, return_date))
        
        cancelled_count = cursor.rowcount
        
        # Log the early return
        log_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO substitute_log (id, tenant_id, absence_id, event_type, staff_id, details, created_at)
            VALUES (?, ?, ?, 'early_return', ?, ?, ?)
        """, (log_id, TENANT_ID, absence_id, staff_id, 
              f'{{"return_date": "{return_date}", "cancelled_requests": {cancelled_count}}}',
              datetime.now().isoformat()))
        
        conn.commit()
        
        # TODO: Send push notifications to cancelled subs
    
    return redirect(url_for('substitute.absence_status', absence_id=absence_id))


@substitute_bp.route('/status/<absence_id>')
def absence_status(absence_id):
    """View status of an absence."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            WHERE a.id = ?
        """, (absence_id,))
        absence = cursor.fetchone()
        if not absence:
            return "Absence not found", 404
        absence = dict(absence)
        
        cursor.execute("""
            SELECT sr.*, p.period_name, p.period_number, p.start_time, p.end_time,
                   sub.display_name as substitute_name
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            LEFT JOIN staff sub ON sr.substitute_id = sub.id
            WHERE sr.absence_id = ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (absence_id,))
        requests = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT * FROM substitute_log
            WHERE absence_id = ?
            ORDER BY created_at ASC
        """, (absence_id,))
        events = [dict(row) for row in cursor.fetchall()]
    
    return render_template('substitute/status.html',
                          absence=absence,
                          requests=requests,
                          events=events)


@substitute_bp.route('/mission-control')
def mission_control():
    """Principal's view - all absences and coverage status."""
    role = session.get('role', 'teacher')
    if role not in ['principal', 'deputy', 'admin']:
        return "Access denied", 403
    
    today = date.today()
    date_range = request.args.get('range', 'today')
    
    if date_range == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    else:
        start_date = today
        end_date = today
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name, s.surname,
                   mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.absence_date >= ? AND a.absence_date <= ? AND a.tenant_id = ?
            ORDER BY a.absence_date DESC, a.reported_at DESC
        """, (start_date.isoformat(), end_date.isoformat(), TENANT_ID))
        absences = [dict(row) for row in cursor.fetchall()]
        
        for absence in absences:
            cursor.execute("""
                SELECT sr.*, p.period_name, p.period_number,
                       sub.display_name as substitute_name
                FROM substitute_request sr
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN staff sub ON sr.substitute_id = sub.id
                WHERE sr.absence_id = ?
                ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
            """, (absence['id'],))
            absence['requests'] = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT * FROM substitute_config WHERE tenant_id = ?
        """, (TENANT_ID,))
        row = cursor.fetchone()
        config = dict(row) if row else {}
        
        total_absences = len(absences)
        fully_covered = sum(1 for a in absences if a['status'] == 'Covered')
        partial = sum(1 for a in absences if a['status'] == 'Partial')
        escalated = sum(1 for a in absences if a['status'] == 'Escalated')
    
    # Build navigation
    nav_header = get_nav_header("Mission Control", "/dashboard/", "Dashboard")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/mission_control.html',
                          absences=absences,
                          config=config,
                          cycle_day=get_cycle_day(),
                          today=today.isoformat(),
                          stats={
                              'total': total_absences,
                              'covered': fully_covered,
                              'partial': partial,
                              'escalated': escalated
                          },
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@substitute_bp.route('/my-assignments')
def my_assignments():
    """Substitute teacher's view - their assignments for today."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    today = date.today().isoformat()
    cycle_day = get_cycle_day()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   v.venue_code
            FROM timetable_slot t
            JOIN period p ON t.period_id = p.id
            LEFT JOIN venue v ON t.venue_id = v.id
            WHERE t.staff_id = ? AND t.cycle_day = ?
            ORDER BY p.sort_order
        """, (staff_id, cycle_day))
        normal_schedule = {row['period_number']: dict(row) for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT sr.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   a.staff_id as absent_staff_id, s.display_name as absent_teacher
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN period p ON sr.period_id = p.id
            WHERE sr.substitute_id = ? AND a.absence_date = ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (staff_id, today))
        assignments = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT period_number, period_name, start_time, end_time
            FROM period
            WHERE tenant_id = ? AND is_teaching = 1
            ORDER BY sort_order
        """, (TENANT_ID,))
        all_periods = [dict(row) for row in cursor.fetchall()]
        
        schedule = []
        assignment_periods = {a['period_number']: a for a in assignments if a['period_number']}
        
        for period in all_periods:
            p_num = period['period_number']
            entry = {
                'period_number': p_num,
                'period_name': period['period_name'],
                'start_time': period['start_time'],
                'end_time': period['end_time'],
                'is_substitute': False,
                'is_free': True
            }
            
            if p_num in assignment_periods:
                a = assignment_periods[p_num]
                entry['is_substitute'] = True
                entry['is_free'] = False
                entry['class_name'] = a['class_name']
                entry['subject'] = a['subject']
                entry['venue'] = a['venue_name']
                entry['absent_teacher'] = a['absent_teacher']
                entry['request_id'] = a['id']
            elif p_num in normal_schedule:
                n = normal_schedule[p_num]
                entry['is_free'] = False
                entry['class_name'] = n['class_name']
                entry['subject'] = n['subject']
                entry['venue'] = n['venue_code']
            
            schedule.append(entry)
        
        mentor_duty = next((a for a in assignments if a['is_mentor_duty']), None)
    
    back_url, back_label = get_back_url_for_user()
    nav_header = get_nav_header("My Assignments", "/substitute/", "Substitutes")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/my_assignments.html',
                          schedule=schedule,
                          mentor_duty=mentor_duty,
                          today=today,
                          cycle_day=cycle_day,
                          sub_count=len(assignments),
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@substitute_bp.route('/decline/<request_id>', methods=['POST'])
def decline_assignment(request_id):
    """Substitute declines an assignment."""
    staff_id = session.get('staff_id')
    reason = request.form.get('reason', 'No reason given')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE substitute_request
            SET status = 'Declined', declined_at = ?, declined_by_id = ?, decline_reason = ?
            WHERE id = ? AND substitute_id = ?
        """, (datetime.now().isoformat(), staff_id, reason, request_id, staff_id))
        conn.commit()
    
    return redirect(url_for('substitute.my_assignments'))


@substitute_bp.route('/log/<absence_id>')
def absence_log(absence_id):
    """Get event log for an absence (for HTMX polling)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sl.*, s.display_name as staff_name
            FROM substitute_log sl
            LEFT JOIN staff s ON sl.staff_id = s.id
            WHERE sl.absence_id = ?
            ORDER BY sl.created_at ASC
        """, (absence_id,))
        events = [dict(row) for row in cursor.fetchall()]
    
    return render_template('substitute/partials/event_log.html', events=events)
