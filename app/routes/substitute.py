"""
Substitute routes - Report absence, view assignments, Substitute Overview
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
        return '/', 'Home'
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
            
            if row and not request.args.get('new'):
                # Active absence exists - redirect to status page
                return redirect(url_for('substitute.absence_status', absence_id=row['id']))
            
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
    
    # Handle duty clashes - reassign duties where absent teacher was assigned
    try:
        from app.services.substitute_engine import handle_absent_teacher_duties
        duty_clash_results = handle_absent_teacher_duties(staff_id, start_date, end_date)
        print(f"Duty clash handling: {duty_clash_results}")
    except Exception as e:
        print(f"Duty clash handling error: {e}")
    
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
    
    # end_date = day before return (teacher is NOT absent on return day)
    return_dt = datetime.strptime(return_date, '%Y-%m-%d').date()
    adjusted_end_date = (return_dt - timedelta(days=1)).isoformat()
    
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
        
        # Guard: if return_date is on or before absence start, clamp to valid range
        absence_start = absence['absence_date']
        if adjusted_end_date < absence_start:
            adjusted_end_date = absence_start
        
        # Update absence record
        cursor.execute("""
            UPDATE absence 
            SET returned_early = 1, 
                returned_at = ?,
                return_reported_by_id = ?,
                end_date = ?,
                status = 'Resolved',
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), staff_id, adjusted_end_date, datetime.now().isoformat(), absence_id))
        
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
        
        # Restore terrain/homework duties from return_date onwards
        cursor.execute("""
            UPDATE duty_roster
            SET replacement_id = NULL, updated_at = datetime('now')
            WHERE staff_id = ? AND duty_date >= ? AND replacement_id IS NOT NULL
        """, (staff_id, return_date))
        restored_duties = cursor.rowcount
        
        # Log the early return
        log_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO substitute_log (id, tenant_id, absence_id, event_type, staff_id, details, created_at)
            VALUES (?, ?, ?, 'early_return', ?, ?, ?)
        """, (log_id, TENANT_ID, absence_id, staff_id, 
              f'{{"return_date": "{return_date}", "cancelled_requests": {cancelled_count}, "restored_duties": {restored_duties}}}',
              datetime.now().isoformat()))
        
        conn.commit()
        
        # TODO: Send push notifications to cancelled subs
    
    return redirect(url_for('substitute.absence_status', absence_id=absence_id))




@substitute_bp.route('/mark-back', methods=['POST'])
def mark_back():
    """Management marks a teacher as returned - cancels remaining substitute assignments."""
    role = session.get('role')
    if role not in ['principal', 'deputy', 'office', 'admin']:
        return redirect('/')
    
    absence_id = request.form.get('absence_id')
    return_date = request.form.get('return_date', date.today().isoformat())
    
    if not absence_id:
        return redirect('/substitute/overview')
    
    # end_date = day before return (teacher is NOT absent on return day)
    return_dt = datetime.strptime(return_date, '%Y-%m-%d').date()
    adjusted_end_date = (return_dt - timedelta(days=1)).isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verify absence exists
        cursor.execute("SELECT id, staff_id, absence_date FROM absence WHERE id = ?", (absence_id,))
        absence = cursor.fetchone()
        
        if not absence:
            return redirect('/substitute/overview')
        
        # Guard: if return_date is on or before absence start, clamp to valid range
        absence_start = absence['absence_date']
        if adjusted_end_date < absence_start:
            adjusted_end_date = absence_start
        
        reported_by_id = session.get('staff_id') or 'management'
        
        # Update absence record
        cursor.execute("""
            UPDATE absence 
            SET returned_early = 1, 
                returned_at = ?,
                return_reported_by_id = ?,
                end_date = ?,
                status = 'Resolved',
                updated_at = ?
            WHERE id = ?
        """, (datetime.now().isoformat(), reported_by_id, adjusted_end_date, 
              datetime.now().isoformat(), absence_id))
        
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
        
        # Restore terrain/homework duties from return_date onwards
        cursor.execute("""
            UPDATE duty_roster
            SET replacement_id = NULL, updated_at = datetime('now')
            WHERE staff_id = ? AND duty_date >= ? AND replacement_id IS NOT NULL
        """, (absence['staff_id'], return_date))
        restored_duties = cursor.rowcount
        
        # Log it
        cursor.execute("""
            INSERT INTO substitute_log (id, tenant_id, absence_id, event_type, staff_id, details, created_at)
            VALUES (?, ?, ?, 'early_return', ?, ?, ?)
        """, (str(uuid.uuid4()), TENANT_ID, absence_id, reported_by_id,
              f'{{"return_date": "{return_date}", "cancelled_requests": {cancelled_count}, "marked_by": "management"}}',
              datetime.now().isoformat()))
        
        conn.commit()
    
    return redirect('/substitute/overview')


@substitute_bp.route('/overview-partial')
def substitute_overview_partial():
    """HTMX partial - returns just the stats + absence cards for polling."""
    day1, day1_label, day2, day2_label = get_school_days()
    today = date.today()
    tab = request.args.get('tab', 'today')

    if tab == 'tomorrow':
        filter_start = day2; filter_end = day2
        filter_dates = [day2.isoformat()]
    elif tab == 'week':
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        filter_start = monday; filter_end = friday
        filter_dates = [(monday + timedelta(days=i)).isoformat() for i in range(5)]
    elif tab == 'nextweek':
        days_until_next_monday = 7 - today.weekday() if today.weekday() != 0 else 7
        next_monday = today + timedelta(days=days_until_next_monday)
        next_friday = next_monday + timedelta(days=4)
        filter_start = next_monday; filter_end = next_friday
        filter_dates = [(next_monday + timedelta(days=i)).isoformat() for i in range(5)]
    else:
        filter_start = day1; filter_end = day1
        filter_dates = [day1.isoformat()]

    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT a.*, s.display_name as teacher_name, s.surname,
                   mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.tenant_id = ?
              AND a.absence_date <= ?
              AND (COALESCE(a.end_date, a.absence_date) >= ? OR a.is_open_ended = 1)
              AND a.status NOT IN ('Resolved', 'Cancelled')
        """
        params = [TENANT_ID, filter_end.isoformat(), filter_start.isoformat()]
        query += " ORDER BY a.absence_date ASC, a.reported_at ASC"
        cursor.execute(query, params)
        absences = [dict(row) for row in cursor.fetchall()]

        for absence in absences:
            placeholders = ','.join(['?' for _ in filter_dates])
            cursor.execute(f"""
                SELECT sr.*, p.period_name, p.period_number,
                       sub.display_name as substitute_name, sc.cycle_day
                FROM substitute_request sr
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN staff sub ON sr.substitute_id = sub.id
                LEFT JOIN school_calendar sc ON sr.request_date = sc.date AND sc.tenant_id = sr.tenant_id
                WHERE sr.absence_id = ?
                  AND sr.request_date IN ({placeholders})
                  AND sr.status IN ('Pending', 'Assigned')
                ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
            """, (absence['id'], *filter_dates))
            absence['requests'] = [dict(row) for row in cursor.fetchall()]

            # Get duty coverage for this absent teacher
            cursor.execute(f"""
                SELECT dr.duty_date, dr.duty_type, dr.status as duty_status,
                       dr.replacement_id,
                       ta.area_name,
                       rep.display_name as replacement_name
                FROM duty_roster dr
                LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
                LEFT JOIN staff rep ON dr.replacement_id = rep.id
                WHERE dr.staff_id = ?
                  AND dr.duty_date IN ({placeholders})
                  AND dr.tenant_id = ?
                  AND dr.replacement_id IS NOT NULL
                ORDER BY dr.duty_date, dr.duty_type
            """, (absence['staff_id'], *filter_dates, TENANT_ID))
            absence['duties'] = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM substitute_config WHERE tenant_id = ?", (TENANT_ID,))
        row = cursor.fetchone()
        config = dict(row) if row else {}

        total_absences = len(absences)
        total_periods = 0; covered_periods = 0; pending_periods = 0
        for absence in absences:
            for req in absence.get('requests', []):
                total_periods += 1
                if req.get('substitute_id'): covered_periods += 1
                else: pending_periods += 1

    return render_template('substitute/partials/mission_control_content.html',
                          absences=absences, config=config,
                          cycle_day=get_cycle_day(),
                          today_iso=today.isoformat(),
                          stats={'total': total_periods, 'covered': covered_periods,
                                 'pending': pending_periods, 'absences': total_absences},
                          filter_start=filter_start.strftime('%a %d %b'),
                          filter_end=filter_end.strftime('%a %d %b'))


@substitute_bp.route('/status/<absence_id>')
def absence_status(absence_id):
    """View status of an absence - summary totals."""
    import json
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
        
        # Teaching period summary
        cursor.execute("""
            SELECT sr.status, sr.is_mentor_duty, p.period_name,
                   sub.display_name as substitute_name,
                   sr.class_name, sr.venue_name
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            LEFT JOIN staff sub ON sr.substitute_id = sub.id
            WHERE sr.absence_id = ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (absence_id,))
        requests = [dict(row) for row in cursor.fetchall()]
        
        # Split into mentor and teaching
        mentor_req = [r for r in requests if r['is_mentor_duty']]
        teaching_reqs = [r for r in requests if not r['is_mentor_duty']]
        
        periods_covered = len([r for r in teaching_reqs if r['status'] == 'Assigned'])
        periods_total = len(teaching_reqs)
        periods_cancelled = len([r for r in teaching_reqs if r['status'] == 'Cancelled'])
        uncovered = [r for r in teaching_reqs if r['status'] == 'Pending']
        
        mentor_info = None
        if mentor_req:
            m = mentor_req[0]
            mentor_info = {
                'substitute_name': m['substitute_name'],
                'venue': m['venue_name'] or '',
                'status': m['status']
            }
        
        # Terrain/homework duty coverage (active: from duty_roster, resolved: from duty_decline)
        cursor.execute("""
            SELECT dr.duty_type, dr.duty_date, ta.area_name,
                   rep.display_name as replacement_name
            FROM duty_roster dr
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            LEFT JOIN staff rep ON dr.replacement_id = rep.id
            WHERE dr.staff_id = ? AND dr.replacement_id IS NOT NULL
              AND dr.duty_date >= ? AND dr.duty_date <= COALESCE(?, ?)
        """, (absence['staff_id'], absence['absence_date'],
              absence['end_date'], absence['absence_date']))
        duty_coverage = [dict(row) for row in cursor.fetchall()]
        
        # If resolved (mark-back clears replacement_id), get from duty_decline audit
        if not duty_coverage and absence['status'] == 'Resolved':
            cursor.execute("""
                SELECT dd.duty_type, MIN(dd.duty_date) as duty_date, dd.duty_description
                FROM duty_decline dd
                WHERE dd.staff_id = ? AND dd.reason = 'absent'
                  AND dd.duty_date >= ? AND dd.duty_date <= COALESCE(?, ?)
                GROUP BY dd.duty_type, dd.duty_date
                ORDER BY dd.duty_date
            """, (absence['staff_id'], absence['absence_date'],
                  absence['end_date'], absence['absence_date']))
            for row in cursor.fetchall():
                d = dict(row)
                desc = d['duty_description'] or ''
                area = desc.split(' - ')[0] if ' - ' in desc else desc
                duty_coverage.append({
                    'duty_type': d['duty_type'],
                    'duty_date': d['duty_date'],
                    'area_name': area if d['duty_type'] == 'terrain' else 'Homework Venue',
                    'replacement_name': None,
                    'was_restored': True
                })
        
        terrain_duties = [d for d in duty_coverage if d['duty_type'] == 'terrain']
        homework_duties = [d for d in duty_coverage if d['duty_type'] == 'homework']
        
        # Check for early_return log to detect mark-back
        cursor.execute("""
            SELECT details FROM substitute_log
            WHERE absence_id = ? AND event_type IN ('early_return', 'mark_back')
            ORDER BY created_at DESC LIMIT 1
        """, (absence_id,))
        return_log = cursor.fetchone()
        
        return_info = None
        if return_log and return_log['details']:
            try:
                return_info = json.loads(return_log['details'])
            except:
                return_info = {}
        
        # Format dates for display
        try:
            from datetime import datetime as dt
            start_dt = dt.strptime(absence['absence_date'], '%Y-%m-%d')
            absence['start_display'] = start_dt.strftime('%a %d %b')
            if absence['end_date']:
                end_dt = dt.strptime(absence['end_date'], '%Y-%m-%d')
                absence['end_display'] = end_dt.strftime('%a %d %b')
        except:
            absence['start_display'] = absence['absence_date']
            absence['end_display'] = absence.get('end_date', '')
    
    # Determine caller context for back button
    role = session.get('role', 'teacher')
    staff_id = session.get('staff_id')
    is_own = absence['staff_id'] == staff_id
    
    return render_template('substitute/status.html',
                          absence=absence,
                          periods_covered=periods_covered,
                          periods_total=periods_total,
                          periods_cancelled=periods_cancelled,
                          uncovered=uncovered,
                          mentor_info=mentor_info,
                          terrain_duties=terrain_duties,
                          homework_duties=homework_duties,
                          return_info=return_info,
                          is_own=is_own,
                          role=role)


@substitute_bp.route('/overview')
def substitute_overview():
    """Principal's view - all absences and coverage status."""
    # All staff can view substitute coverage
    
    # Get school days (skips weekends)
    day1, day1_label, day2, day2_label = get_school_days()
    today = date.today()
    tab = request.args.get('tab', 'today')
    staff_filter = request.args.get('staff', None)
    
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
        query = """
            SELECT a.*, s.display_name as teacher_name, s.surname,
                   mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.tenant_id = ?
              AND a.absence_date <= ?
              AND (COALESCE(a.end_date, a.absence_date) >= ? OR a.is_open_ended = 1)
              AND a.status NOT IN ('Resolved', 'Cancelled')
        """
        params = [TENANT_ID, filter_end.isoformat(), filter_start.isoformat()]
        
        if staff_filter:
            query += " AND a.staff_id = ?"
            params.append(staff_filter)
        
        query += " ORDER BY a.absence_date ASC, a.reported_at ASC"
        cursor.execute(query, params)
        absences = [dict(row) for row in cursor.fetchall()]
        
        for absence in absences:
            # Get requests only for dates within filter range
            placeholders = ','.join(['?' for _ in filter_dates])
            cursor.execute(f"""
                SELECT sr.*, p.period_name, p.period_number,
                       sub.display_name as substitute_name, sc.cycle_day
                FROM substitute_request sr
                LEFT JOIN period p ON sr.period_id = p.id
                LEFT JOIN staff sub ON sr.substitute_id = sub.id
                LEFT JOIN school_calendar sc ON sr.request_date = sc.date AND sc.tenant_id = sr.tenant_id
                WHERE sr.absence_id = ?
                  AND sr.request_date IN ({placeholders})
                  AND sr.status IN ('Pending', 'Assigned')
                ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
            """, (absence['id'], *filter_dates))
            absence['requests'] = [dict(row) for row in cursor.fetchall()]

            # Get duty coverage for this absent teacher
            cursor.execute(f"""
                SELECT dr.duty_date, dr.duty_type, dr.status as duty_status,
                       dr.replacement_id,
                       ta.area_name,
                       rep.display_name as replacement_name
                FROM duty_roster dr
                LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
                LEFT JOIN staff rep ON dr.replacement_id = rep.id
                WHERE dr.staff_id = ?
                  AND dr.duty_date IN ({placeholders})
                  AND dr.tenant_id = ?
                  AND dr.replacement_id IS NOT NULL
                ORDER BY dr.duty_date, dr.duty_type
            """, (absence['staff_id'], *filter_dates, TENANT_ID))
            absence['duties'] = [dict(row) for row in cursor.fetchall()]
        
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
    if staff_filter:
        nav_header = get_nav_header("Substitute Overview", "/absences/teachers", "Back")
    else:
        nav_header = get_nav_header("Substitute Overview", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/mission_control.html',
                          absences=absences,
                          config=config,
                          cycle_day=get_cycle_day(),
                          today=today.strftime('%a %d %b'),
                          today_iso=today.isoformat(),
                          stats={'total': total_periods, 'covered': covered_periods, 
                                 'pending': pending_periods, 'absences': total_absences},
                          nav_header=nav_header,
                          nav_styles=nav_styles,
                          current_tab=tab,
                          filter_start=filter_start.strftime('%a %d %b'),
                          filter_end=filter_end.strftime('%a %d %b'),
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
              f"{req['decliner_name']} declined {req['period_name'] or 'Register'}: {reason}",
              staff_id, TENANT_ID, now.isoformat()))
        
        
        # Also log to unified duty_decline table
        duty_desc = f"{req['period_name'] or 'Register'} - covering for {req.get('absent_teacher_name', 'absent teacher')}"
        cursor.execute("""
            INSERT INTO duty_decline (id, tenant_id, duty_type, staff_id, staff_name, duty_description, duty_date, reason)
            VALUES (?, ?, 'substitute', ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), TENANT_ID, staff_id, req['decliner_name'], duty_desc, req['request_date'], reason))
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
                        req['period_name'] or 'Register',
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


@substitute_bp.route('/sub-duties')
def sub_duties():
    """View all upcoming substitute assignments for the logged-in teacher."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    today = date.today().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all future sub assignments for this teacher
        cursor.execute("""
            SELECT sr.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   s.display_name as absent_teacher, a.absence_type as absence_reason,
                   sr.request_date
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN period p ON sr.period_id = p.id
            WHERE sr.substitute_id = ? 
              AND sr.status = 'Assigned'
              AND sr.request_date >= ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (staff_id, today))
        
        all_assignments = [dict(row) for row in cursor.fetchall()]
        
        # Get cycle days for each unique date
        cursor.execute("SELECT cycle_start_date, cycle_length FROM substitute_config WHERE tenant_id = ?", (TENANT_ID,))
        config_row = cursor.fetchone()
        cycle_start = None
        cycle_length = 7
        if config_row and config_row['cycle_start_date']:
            cycle_start = datetime.strptime(config_row['cycle_start_date'], '%Y-%m-%d').date()
            cycle_length = config_row['cycle_length'] or 7
        
        # Group assignments by date
        assignments_by_date = []
        current_date = None
        current_group = None
        
        for assignment in all_assignments:
            req_date = assignment['request_date']
            if req_date != current_date:
                if current_group:
                    assignments_by_date.append(current_group)
                
                # Calculate cycle day
                cycle_day = None
                if cycle_start:
                    try:
                        d = datetime.strptime(req_date, '%Y-%m-%d').date()
                        days_diff = (d - cycle_start).days
                        if days_diff >= 0:
                            cycle_day = (days_diff % cycle_length) + 1
                    except:
                        pass
                
                # Format display date
                try:
                    d = datetime.strptime(req_date, '%Y-%m-%d')
                    display_date = d.strftime('%A, %d %b')
                except:
                    display_date = req_date
                
                current_group = {
                    'date': req_date,
                    'display_date': display_date,
                    'cycle_day': cycle_day,
                    'assignments': []
                }
                current_date = req_date
            
            current_group['assignments'].append(assignment)
        
        if current_group:
            assignments_by_date.append(current_group)
    
    total_count = len(all_assignments)
    days_count = len(assignments_by_date)
    
    nav_header = get_nav_header("Sub Duties", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('substitute/sub_duties.html',
                          assignments_by_date=assignments_by_date,
                          total_count=total_count,
                          days_count=days_count,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@substitute_bp.route('/mark-absent')
def mark_absent():
    """Management/Office: Search and mark a teacher absent."""
    # Check permission - only management and office
    role = session.get('role')
    if role not in ['principal', 'deputy', 'office', 'admin']:
        return redirect('/')
    
    # Get all teaching staff for search
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, display_name,
                   LOWER(SUBSTR(display_name, INSTR(display_name, ' ') + 1)) as sort_name
            FROM staff
            WHERE tenant_id = ? AND is_active = 1
            ORDER BY display_name
        """, (TENANT_ID,))
        all_staff = [dict(row) for row in cursor.fetchall()]
    
    return render_template('substitute/mark_absent.html',
                          all_staff=all_staff,
                          today=date.today().isoformat())


@substitute_bp.route('/mark-absent/submit', methods=['POST'])
def mark_absent_submit():
    """Process absence reported by management/office."""
    # Check permission
    role = session.get('role')
    if role not in ['principal', 'deputy', 'office', 'admin']:
        return redirect('/')
    
    staff_id = request.form.get('staff_id')
    if not staff_id:
        return redirect('/substitute/mark-absent')
    
    absence_type = request.form.get('absence_type', 'Sick')
    start_date = request.form.get('start_date', date.today().isoformat())
    end_date = request.form.get('end_date', start_date)
    is_full_day = request.form.get('is_full_day', '1') == '1'
    
    # Create absence using existing function
    absence_id = create_absence_multiday(
        staff_id=staff_id,
        start_date=start_date,
        end_date=end_date,
        is_open_ended=False,
        absence_type=absence_type,
        reason=f"Reported by {session.get('display_name', 'Office')}",
        is_full_day=is_full_day
    )
    
    # Process and assign substitutes
    results = process_absence(absence_id)
    
    # Handle duty clashes - reassign duties where absent teacher was assigned
    try:
        from app.services.substitute_engine import handle_absent_teacher_duties
        duty_clash_results = handle_absent_teacher_duties(staff_id, start_date, end_date)
        print(f"Management mark-absent duty clash handling: {duty_clash_results}")
    except Exception as e:
        print(f"Management mark-absent duty clash error: {e}")
    
    return redirect('/substitute/status/' + absence_id)
