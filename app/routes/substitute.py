"""
Substitute routes - Report absence, view assignments, Mission Control
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from datetime import date, datetime, timedelta
from app.services.db import get_connection
from app.services.substitute_engine import (
    create_absence, process_absence, get_cycle_day,
    get_teacher_schedule, get_current_pointer
)

substitute_bp = Blueprint('substitute', __name__, url_prefix='/substitute')

TENANT_ID = "MARAGON"


@substitute_bp.route('/')
def index():
    """Substitute home - links to report absence or view assignments."""
    staff_id = session.get('staff_id')
    display_name = session.get('display_name', 'Teacher')
    
    return render_template('substitute/index.html',
                          staff_id=staff_id,
                          display_name=display_name)


@substitute_bp.route('/report', methods=['GET', 'POST'])
def report_absence():
    """Teacher reports their own absence."""
    staff_id = session.get('staff_id')
    
    if not staff_id:
        return redirect('/?u=beatrix')  # For demo, redirect to login
    
    if request.method == 'GET':
        # Get periods for partial day selection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, period_number, period_name, start_time, end_time
                FROM period 
                WHERE tenant_id = ? AND is_teaching = 1
                ORDER BY sort_order
            """, (TENANT_ID,))
            periods = [dict(row) for row in cursor.fetchall()]
        
        return render_template('substitute/report.html',
                              periods=periods,
                              today=date.today().isoformat())
    
    # POST - Create absence and process
    absence_type = request.form.get('absence_type', 'Sick')
    reason = request.form.get('reason', '')
    absence_date = request.form.get('absence_date', date.today().isoformat())
    is_full_day = request.form.get('is_full_day', '1') == '1'
    
    # Create absence record
    absence_id = create_absence(
        staff_id=staff_id,
        absence_date=absence_date,
        absence_type=absence_type,
        reason=reason,
        is_full_day=is_full_day
    )
    
    # Process - find substitutes
    results = process_absence(absence_id)
    
    # Redirect to confirmation/live view
    return redirect(url_for('substitute.absence_status', absence_id=absence_id))


@substitute_bp.route('/status/<absence_id>')
def absence_status(absence_id):
    """View status of an absence - for sick teacher to see their cover."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get absence details
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
        
        # Get substitute requests
        cursor.execute("""
            SELECT sr.*, p.period_name, p.period_number, p.start_time, p.end_time,
                   sub.display_name as substitute_name
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            LEFT JOIN staff sub ON sr.substitute_id = sub.id
            WHERE sr.absence_id = ?
            ORDER BY sr.is_mentor_duty DESC, p.sort_order
        """, (absence_id,))
        requests = [dict(row) for row in cursor.fetchall()]
        
        # Get event log
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
    
    # Calculate date filter
    if date_range == 'week':
        # Get start of week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = today
    else:
        start_date = today
        end_date = today
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get absences in date range
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
        
        # Get substitute requests for each absence
        for absence in absences:
            cursor.execute("""
                SELECT sr.*, p.period_name, p.period_number,
                       sub.display_name as substitute_name
                FROM substitute_request sr
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN staff sub ON sr.substitute_id = sub.id
                WHERE sr.absence_id = ?
                ORDER BY sr.is_mentor_duty DESC, p.sort_order
            """, (absence['id'],))
            absence['requests'] = [dict(row) for row in cursor.fetchall()]
        
        # Get current config
        cursor.execute("""
            SELECT * FROM substitute_config WHERE tenant_id = ?
        """, (TENANT_ID,))
        row = cursor.fetchone()
        config = dict(row) if row else {}
        
        # Summary stats
        total_absences = len(absences)
        fully_covered = sum(1 for a in absences if a['status'] == 'Covered')
        partial = sum(1 for a in absences if a['status'] == 'Partial')
        escalated = sum(1 for a in absences if a['status'] == 'Escalated')
    
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
                          })
def my_assignments():
    """Substitute teacher's view - their assignments for today."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    today = date.today().isoformat()
    cycle_day = get_cycle_day()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get normal schedule
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
        
        # Get substitute assignments for today
        cursor.execute("""
            SELECT sr.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   a.staff_id as absent_staff_id, s.display_name as absent_teacher
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN period p ON sr.period_id = p.id
            WHERE sr.substitute_id = ? AND a.absence_date = ?
            ORDER BY sr.is_mentor_duty DESC, p.sort_order
        """, (staff_id, today))
        assignments = [dict(row) for row in cursor.fetchall()]
        
        # Get all periods
        cursor.execute("""
            SELECT period_number, period_name, start_time, end_time
            FROM period
            WHERE tenant_id = ? AND is_teaching = 1
            ORDER BY sort_order
        """, (TENANT_ID,))
        all_periods = [dict(row) for row in cursor.fetchall()]
        
        # Build combined schedule
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
                # Substitute duty
                a = assignment_periods[p_num]
                entry['is_substitute'] = True
                entry['is_free'] = False
                entry['class_name'] = a['class_name']
                entry['subject'] = a['subject']
                entry['venue'] = a['venue_name']
                entry['absent_teacher'] = a['absent_teacher']
                entry['request_id'] = a['id']
            elif p_num in normal_schedule:
                # Normal teaching
                n = normal_schedule[p_num]
                entry['is_free'] = False
                entry['class_name'] = n['class_name']
                entry['subject'] = n['subject']
                entry['venue'] = n['venue_code']
            
            schedule.append(entry)
        
        # Check for mentor duty
        mentor_duty = next((a for a in assignments if a['is_mentor_duty']), None)
    
    return render_template('substitute/my_assignments.html',
                          schedule=schedule,
                          mentor_duty=mentor_duty,
                          today=today,
                          cycle_day=cycle_day,
                          sub_count=len(assignments))


@substitute_bp.route('/decline/<request_id>', methods=['POST'])
def decline_assignment(request_id):
    """Substitute declines an assignment."""
    staff_id = session.get('staff_id')
    reason = request.form.get('reason', 'No reason given')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Update request
        cursor.execute("""
            UPDATE substitute_request
            SET status = 'Declined', declined_at = ?, declined_by_id = ?, decline_reason = ?
            WHERE id = ? AND substitute_id = ?
        """, (datetime.now().isoformat(), staff_id, reason, request_id, staff_id))
        conn.commit()
        
        # TODO: Trigger reassignment logic
        # For now, just log it
    
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
