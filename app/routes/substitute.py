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


def get_school_days():
    """
    Returns (day1, day1_label, day2, day2_label) for Today/Tomorrow tabs.
    Skips weekends - if today is Sat/Sun, day1 = Monday.
    """
    today = date.today()
    weekday = today.weekday()  # Mon=0, Tue=1, ..., Fri=4, Sat=5, Sun=6
    
    # Find first school day (day1)
    if weekday == 5:  # Saturday
        day1 = today + timedelta(days=2)  # Monday
    elif weekday == 6:  # Sunday
        day1 = today + timedelta(days=1)  # Monday
    else:
        day1 = today
    
    # Find second school day (day2)
    if day1.weekday() == 4:  # Friday
        day2 = day1 + timedelta(days=3)  # Monday
    else:
        day2 = day1 + timedelta(days=1)
    
    # Generate labels
    if day1 == today:
        day1_label = f"Today ({day1.strftime('%a %d')})"
    else:
        day1_label = day1.strftime('%a %d %b')
    
    if day2 == today + timedelta(days=1) and today.weekday() < 4:
        day2_label = f"Tomorrow ({day2.strftime('%a %d')})"
    else:
        day2_label = day2.strftime('%a %d %b')
    
    return day1, day1_label, day2, day2_label


def get_back_url_for_user():
    """Get appropriate back URL based on user role."""
    role = session.get('role', 'teacher')
    if role in ['principal', 'deputy', 'admin']:
        return '/dashboard/', 'Dashboard'
    return '/', 'Home'


@substitute_bp.route('/')
def index():
    """Redirect to report form."""
    return redirect('/substitute/report')


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
    
    # Send push notification to principal (Pierre)
    try:
        from app.routes.push import send_absence_reported_push
        staff_name = results.get('sick_teacher', {}).get('name', 'A teacher')
        total_periods = sum(len(day.get('periods', [])) for day in results.get('days', []))
        date_display = ', '.join(day.get('date_display', '') for day in results.get('days', []))
        send_absence_reported_push(staff_name, date_display, total_periods)
    except Exception as e:
        print(f'Pierre push error: {e}')
    
    # Send push notifications to substitutes and absent teacher
    try:
        from app.routes.push import send_substitute_assigned_push, send_absence_covered_push
        print(f"DEBUG: Starting push notifications for absence")
        print(f"DEBUG: Results days: {len(results.get('days', []))}")
        
        for day in results.get('days', []):
            date_display = day.get('date_display', '')
            print(f"DEBUG: Day {date_display} has {len(day.get('periods', []))} periods")
            for period in day.get('periods', []):
                print(f"DEBUG: Period {period.get('period_name')} sub_id={period.get('substitute_id')}")
                if period.get('substitute_id'):
                    print(f"DEBUG: Sending push to {period.get('substitute_id')}")
                    send_substitute_assigned_push(
                        period['substitute_id'],
                        results['sick_teacher']['name'],
                        period['period_name'],
                        date_display,
                        period.get('venue', 'TBC')
                    )
        
        date_range = results.get('date_range', {})
        range_str = date_range.get('start', '')[:10]
        if date_range.get('end') and date_range.get('end') != date_range.get('start'):
            range_str += ' - ' + date_range.get('end', '')[:10]
        send_absence_covered_push(
            staff_id,
            results.get('covered_count', 0),
            results.get('total_count', 0),
            range_str
        )
    except Exception as e:
        print(f'Substitute push error: {e}')
    
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
    
    # Get school days (skips weekends)
    day1, day1_label, day2, day2_label = get_school_days()
    today = date.today()
    tab = request.args.get('tab', 'today')
    
    # Calculate date range based on tab
    if tab == 'tomorrow':
        filter_start = day2
        filter_end = day2
        filter_dates = [day2.isoformat()]
    elif tab == 'week':
        # Monday to Friday of current week
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        filter_start = monday
        filter_end = friday
        filter_dates = [(monday + timedelta(days=i)).isoformat() for i in range(5)]
    elif tab == 'nextweek':
        # Monday to Friday of next week
        days_until_next_monday = 7 - today.weekday() if today.weekday() != 0 else 7
        next_monday = today + timedelta(days=days_until_next_monday)
        next_friday = next_monday + timedelta(days=4)
        filter_start = next_monday
        filter_end = next_friday
        filter_dates = [(next_monday + timedelta(days=i)).isoformat() for i in range(5)]
    else:  # today
        filter_start = day1
        filter_end = day1
        filter_dates = [day1.isoformat()]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get absences that overlap with filter range
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name, s.surname,
                   mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.tenant_id = ?
              AND a.absence_date <= ?
              AND (COALESCE(a.end_date, a.absence_date) >= ? OR a.is_open_ended = 1)
            ORDER BY a.absence_date DESC, a.reported_at DESC
        """, (TENANT_ID, filter_end.isoformat(), filter_start.isoformat()))
        absences = [dict(row) for row in cursor.fetchall()]
        
        for absence in absences:
            # Get requests only for dates within filter range
            placeholders = ','.join(['?' for _ in filter_dates])
            cursor.execute(f"""
                SELECT sr.*, p.period_name, p.period_number,
                       sub.display_name as substitute_name
                FROM substitute_request sr
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN staff sub ON sr.substitute_id = sub.id
                WHERE sr.absence_id = ?
                  AND sr.request_date IN ({placeholders})
                ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
            """, (absence['id'], *filter_dates))
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
        
        # Period-level stats for the filtered view
        total_periods = 0
        covered_periods = 0
        pending_periods = 0
        for absence in absences:
            for req in absence.get('requests', []):
                total_periods += 1
                if req.get('substitute_id'):
                    covered_periods += 1
                else:
                    pending_periods += 1
    
    # Build navigation
    nav_header = get_nav_header("Mission Control", "/dashboard/", "Dashboard")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/mission_control.html',
                          absences=absences,
                          config=config,
                          cycle_day=get_cycle_day(),
                          today=today.strftime('%a %d %b'),
                          stats={'total': total_periods, 'covered': covered_periods, 
                                 'pending': pending_periods, 'absences': total_absences},
                          nav_header=nav_header,
                          nav_styles=nav_styles,
                          current_tab=tab,
                          filter_start=filter_start.strftime('%a %d %b'),
                          filter_end=filter_end.strftime('%a %d %b'),
                          tab1_label=day1_label,
                          tab2_label=day2_label)


@substitute_bp.route('/my-assignments')
def my_assignments():
    """Substitute teacher's view - their schedule with sub duties."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    # Get school days (skips weekends)
    day1, day1_label, day2, day2_label = get_school_days()
    
    # Handle Today/Tomorrow tabs
    tab = request.args.get('tab', 'today')
    
    if tab == 'tomorrow':
        target_date = day2
    else:
        target_date = day1
    
    target_date_str = target_date.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get cycle day for target date
        cursor.execute("SELECT cycle_start_date, cycle_length FROM substitute_config WHERE tenant_id = ?", (TENANT_ID,))
        config_row = cursor.fetchone()
        
        if config_row and config_row['cycle_start_date']:
            start = datetime.strptime(config_row['cycle_start_date'], '%Y-%m-%d').date()
            cycle_length = config_row['cycle_length'] or 7
            days_diff = (target_date - start).days
            cycle_day = (days_diff % cycle_length) + 1
        else:
            cycle_day = 1
        
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
                   a.staff_id as absent_staff_id, s.display_name as absent_teacher, a.absence_type as absence_reason
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN period p ON sr.period_id = p.id
            WHERE sr.substitute_id = ? AND sr.request_date = ? AND sr.status = 'Assigned'
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (staff_id, target_date_str))
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
    nav_header = get_nav_header("My Schedule", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/my_assignments.html',
                          schedule=schedule,
                          mentor_duty=mentor_duty,
                          display_date=target_date.strftime('%a %d %b'),
                          cycle_day=cycle_day,
                          sub_count=len(assignments),
                          nav_header=nav_header,
                          nav_styles=nav_styles,
                          current_tab=tab,
                          tab1_label=day1_label,
                          tab2_label=day2_label)


@substitute_bp.route('/decline/<request_id>', methods=['POST'])
def decline_assignment(request_id):
    """Substitute declines an assignment - with 30-min cutoff and auto-reassign."""
    staff_id = session.get('staff_id')
    reason = request.form.get('reason', '').strip() or 'No reason given'
    now = datetime.now()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get the request details
        cursor.execute("""
            SELECT sr.*, p.start_time, p.period_name, a.absence_date, a.id as absence_id,
                   s.display_name as decliner_name
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON sr.substitute_id = s.id
            WHERE sr.id = ? AND sr.substitute_id = ?
        """, (request_id, staff_id))
        req = cursor.fetchone()
        
        if not req:
            return "Assignment not found", 404
        
        req = dict(req)
        
        # Check 30-min cutoff (only for non-mentor duties with a period)
        if req['start_time'] and req['request_date'] == date.today().isoformat():
            period_start = datetime.strptime(f"{req['request_date']} {req['start_time']}", "%Y-%m-%d %H:%M")
            minutes_until = (period_start - now).total_seconds() / 60
            
            # Get cutoff from config
            cursor.execute("SELECT decline_cutoff_minutes FROM substitute_config WHERE tenant_id = ?", (TENANT_ID,))
            config = cursor.fetchone()
            cutoff = config['decline_cutoff_minutes'] if config else 30
            
            if minutes_until < cutoff:
                # Too late to decline
                return render_template('substitute/decline_too_late.html',
                    period_name=req['period_name'],
                    minutes_until=int(minutes_until),
                    cutoff=cutoff), 400
        
        # Mark as declined
        cursor.execute("""
            UPDATE substitute_request
            SET status = 'Declined', declined_at = ?, declined_by_id = ?, decline_reason = ?
            WHERE id = ?
        """, (now.isoformat(), staff_id, reason, request_id))
        
        # Log the decline
        cursor.execute("""
            INSERT INTO substitute_log (id, absence_id, event_type, details, staff_id, tenant_id, created_at)
            VALUES (?, ?, 'declined', ?, ?, ?, ?)
        """, (str(uuid.uuid4()), req['absence_id'], 
              f"{req['decliner_name']} declined {req['period_name'] or 'Roll Call'}: {reason}",
              staff_id, TENANT_ID, now.isoformat()))
        
        conn.commit()
        
        # Auto-reassign
        from app.services.substitute_engine import reassign_declined_request
        new_sub = reassign_declined_request(request_id, staff_id)
        
        if new_sub:
            # Send push notification to new substitute
            try:
                from app.routes.push import send_substitute_assigned_push
                
                # Get absence details for the notification
                cursor.execute("""
                    SELECT a.absence_date, s.display_name as absent_teacher
                    FROM absence a
                    JOIN staff s ON a.staff_id = s.id
                    WHERE a.id = ?
                """, (req['absence_id'],))
                absence_info = cursor.fetchone()
                
                if absence_info:
                    try:
                        date_display = datetime.strptime(absence_info['absence_date'], '%Y-%m-%d').strftime('%a %d %b')
                    except:
                        date_display = absence_info['absence_date']
                    
                    send_substitute_assigned_push(
                        new_sub['id'],
                        absence_info['absent_teacher'],
                        req['period_name'] or 'Roll Call',
                        date_display,
                        req.get('venue_name', 'TBC')
                    )
                    print(f"PUSH: Sent reassignment notification to {new_sub['display_name']}")
            except Exception as e:
                print(f"Push error on reassignment: {e}")
    
    return_to = request.form.get('return_to', '/')
    return redirect(return_to)


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
