"""
Duty routes - My Day (teacher's full schedule view)
Combines: teaching periods, terrain duty, homework duty, sub assignments, sport duties
"""

from flask import Blueprint, render_template, request, redirect, session
from datetime import date, datetime, timedelta
from app.services.db import get_connection
from app.services.substitute_engine import get_cycle_day
from app.services.nav import get_nav_header, get_nav_styles

duty_bp = Blueprint('duty', __name__, url_prefix='/duty')

TENANT_ID = "MARAGON"


def get_school_days_extended():
    """
    Returns list of 7 school days starting from today (or Monday if weekend).
    Each item: {'date': date_obj, 'label': str, 'tab_id': str}
    Skips weekends automatically.
    """
    today = date.today()
    weekday = today.weekday()  # Mon=0 ... Sun=6
    
    # Start from Monday if today is weekend
    if weekday == 5:  # Saturday
        start = today + timedelta(days=2)
    elif weekday == 6:  # Sunday
        start = today + timedelta(days=1)
    else:
        start = today
    
    days = []
    current = start
    while len(days) < 5:
        if current.weekday() < 5:  # Mon-Fri only
            # Generate label
            if current == today:
                label = "Today"
            elif current == today + timedelta(days=1):
                label = "Tmrw"
            else:
                label = current.strftime('%a %d')  # "Wed 21"
            
            days.append({
                'date': current,
                'label': label,
                'tab_id': current.isoformat()  # "2026-01-19"
            })
        current += timedelta(days=1)
    
    return days


@duty_bp.route('/my-day')
def my_day():
    """Teacher's full daily schedule view."""
    # Check for staff override (leadership viewing another teacher)
    staff_override = request.args.get('staff')
    viewing_other = False
    viewing_name = None
    
    if staff_override:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, display_name FROM staff WHERE id = ? AND tenant_id = ?", (staff_override, TENANT_ID))
            row = cursor.fetchone()
            if row:
                staff_id = row['id']
                viewing_other = True
                viewing_name = row['display_name']
            else:
                return redirect('/timetables/')
    else:
        staff_id = session.get('staff_id')
        if not staff_id:
            return redirect('/')
    
    # Get 7 school days
    school_days = get_school_days_extended()
    
    tab = request.args.get('tab', '')
    
    # Backward compat + default handling
    if tab == 'today' or tab == '':
        target_date = school_days[0]['date']
        tab = school_days[0]['tab_id']
    elif tab == 'tomorrow':
        target_date = school_days[1]['date']
        tab = school_days[1]['tab_id']
    else:
        # Tab is a date string like "2026-01-21"
        try:
            target_date = date.fromisoformat(tab)
        except ValueError:
            target_date = school_days[0]['date']
            tab = school_days[0]['tab_id']
    
    target_date_str = target_date.isoformat()
    weekday = target_date.weekday()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT cycle_day, day_type, bell_schedule, day_name
            FROM school_calendar
            WHERE tenant_id = ? AND date = ?
        """, (TENANT_ID, target_date_str))
        cal_row = cursor.fetchone()
        
        if cal_row:
            cycle_day = cal_row['cycle_day']
            day_type = cal_row['day_type']
            bell_schedule = cal_row['bell_schedule']
            day_name = cal_row['day_name']
        else:
            cycle_day = get_cycle_day()
            day_type = 'academic' if weekday < 5 else 'weekend'
            if weekday in [0, 2]:
                bell_schedule = 'type_a'
            elif weekday in [1, 3]:
                bell_schedule = 'type_b'
            elif weekday == 4:
                bell_schedule = 'type_c'
            else:
                bell_schedule = 'none'
            day_name = f"D{cycle_day}" if cycle_day else None
        
        cursor.execute("""
            SELECT * FROM bell_schedule
            WHERE tenant_id = ? AND schedule_type = ?
            ORDER BY sort_order
        """, (TENANT_ID, bell_schedule))
        bell_slots = [dict(row) for row in cursor.fetchall()]
        
        teaching_slots = {}
        if cycle_day:
            cursor.execute("""
                SELECT t.*, p.period_number, p.period_name, v.venue_code
                FROM timetable_slot t
                JOIN period p ON t.period_id = p.id
                LEFT JOIN venue v ON t.venue_id = v.id
                WHERE t.staff_id = ? AND t.cycle_day = ?
                ORDER BY p.sort_order
            """, (staff_id, cycle_day))
            teaching_slots = {row['period_number']: dict(row) for row in cursor.fetchall()}
        
        # Get teacher's home room
        cursor.execute("""
            SELECT v.id as venue_id, v.venue_code
            FROM staff_venue sv
            JOIN venue v ON sv.venue_id = v.id
            WHERE sv.staff_id = ? AND sv.tenant_id = ?
        """, (staff_id, TENANT_ID))
        home_room_row = cursor.fetchone()
        home_room_id = home_room_row['venue_id'] if home_room_row else None
        home_room_code = home_room_row['venue_code'] if home_room_row else None
        
        # Get roving teachers using this teacher's room (for free period display)
        room_occupants = {}
        if home_room_id and cycle_day:
            cursor.execute("""
                SELECT t.cycle_day, p.period_number, s.display_name as occupant_name
                FROM timetable_slot t
                JOIN period p ON t.period_id = p.id
                JOIN staff s ON t.staff_id = s.id
                WHERE t.venue_id = ? AND t.cycle_day = ? AND t.staff_id != ?
            """, (home_room_id, cycle_day, staff_id))
            for row in cursor.fetchall():
                room_occupants[row['period_number']] = row['occupant_name']
        
        cursor.execute("""
            SELECT dr.*, ta.area_name, ta.area_code
            FROM duty_roster dr
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.staff_id = ? AND dr.duty_date = ? AND dr.duty_type = 'terrain'
        """, (staff_id, target_date_str))
        terrain_row = cursor.fetchone()
        terrain_duty = dict(terrain_row) if terrain_row else None
        
        cursor.execute("""
            SELECT * FROM duty_roster
            WHERE staff_id = ? AND duty_date = ? AND duty_type = 'homework'
        """, (staff_id, target_date_str))
        homework_row = cursor.fetchone()
        homework_duty = dict(homework_row) if homework_row else None
        
        cursor.execute("""
            SELECT sr.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   s.display_name as absent_teacher, sr.venue_name, a.absence_type as absence_reason
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN period p ON sr.period_id = p.id
            WHERE sr.substitute_id = ? AND sr.request_date = ? AND sr.status = 'Assigned'
            ORDER BY sr.is_mentor_duty DESC, p.sort_order
        """, (staff_id, target_date_str))
        sub_assignments = [dict(row) for row in cursor.fetchall()]
        sub_by_period = {a['period_number']: a for a in sub_assignments if a['period_number']}
        mentor_sub = next((a for a in sub_assignments if a['is_mentor_duty']), None)
        
        # Get sport duty for this date
        cursor.execute("""
            SELECT sd.*, se.event_name, se.start_time as event_start, se.end_time as event_end,
                   se.sport_type, se.venue_name, se.affects_timetable, se.id as event_id
            FROM sport_duty sd
            JOIN sport_event se ON sd.event_id = se.id
            WHERE sd.staff_id = ? AND sd.tenant_id = ? AND se.event_date = ?
        """, (staff_id, TENANT_ID, target_date_str))
        sport_duties = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT mg.group_name, g.grade_name
            FROM mentor_group mg
            LEFT JOIN grade g ON mg.grade_id = g.id
            WHERE mg.mentor_id = ?
        """, (staff_id,))
        mentor_row = cursor.fetchone()

        # Check if this teacher is absent on target date
        cursor.execute("""
            SELECT absence_type, status FROM absence
            WHERE staff_id = ? AND tenant_id = ?
            AND absence_date <= ? AND (end_date >= ? OR end_date IS NULL OR is_open_ended = 1)
            AND status IN ('Reported', 'Covered', 'Partial')
            LIMIT 1
        """, (staff_id, TENANT_ID, target_date_str, target_date_str))
        absence_row = cursor.fetchone()
        is_absent = absence_row is not None
        absence_type = absence_row['absence_type'] if absence_row else None
        mentor_group = dict(mentor_row) if mentor_row else None
        
        schedule = []
        
        # Sport duties at top
        for sport in sport_duties:
            schedule.append({
                'slot_type': 'sport',
                'slot_name': sport['event_name'],
                'start_time': sport['event_start'] or '08:00',
                'end_time': sport['event_end'],
                'content': f"{sport['duty_type']}" + (f": {sport['notes']}" if sport.get('notes') else ''),
                'badge': sport['sport_type'],
                'badge_color': 'teal',
                'is_duty': False,
                'is_sub': False,
                'is_free': False,
                'is_free_occupied': False,
                'room_occupant': None,
                'is_sport': True,
                'request_id': None,
                'event_id': sport['event_id'],
                'sport_duty_id': sport['id'],
                'affects_timetable': sport['affects_timetable']
            })
        
        if terrain_duty:
            schedule.append({
                'slot_type': 'duty',
                'slot_name': 'Morning Duty',
                'start_time': '07:15',
                'end_time': '07:30',
                'content': f"Terrain: {terrain_duty['area_name']}",
                'badge': 'DUTY',
                'badge_color': 'blue',
                'is_duty': True,
                'is_sub': False,
                'is_free': False,
                'is_free_occupied': False,
                'room_occupant': None,
                'is_sport': False,
                'request_id': None,
                'terrain_duty_id': terrain_duty['id']
            })
        
        for slot in bell_slots:
            item = {
                'slot_type': slot['slot_type'],
                'slot_name': slot['slot_name'],
                'start_time': slot['start_time'],
                'end_time': slot['end_time'],
                'content': None,
                'badge': None,
                'badge_color': None,
                'is_duty': False,
                'is_sub': False,
                'is_free': False,
                'is_free_occupied': False,
                'room_occupant': None,
                'is_sport': False,
                'request_id': None
            }
            
            if slot['slot_type'] == 'register':
                if mentor_sub:
                    item['content'] = f"Covering for {mentor_sub['absent_teacher']}" + (f" • {mentor_sub['venue_name']}" if mentor_sub.get('venue_name') else "")
                    item['badge'] = 'SUB'
                    item['badge_color'] = 'orange'
                    item['is_sub'] = True
                    item['request_id'] = mentor_sub['id']
                elif mentor_group:
                    item['content'] = mentor_group['group_name']
                else:
                    item['content'] = "Register"
            
            elif slot['slot_type'] == 'assembly':
                item['content'] = "All staff"
            
            elif slot['slot_type'] == 'period':
                p_num = slot['slot_number']
                
                if p_num and p_num in sub_by_period:
                    # Sub duty takes priority
                    sub = sub_by_period[p_num]
                    venue = sub.get('venue_name') or 'TBC'
                    item['content'] = f"{sub.get('class_name', '')} {sub.get('subject', '')} • {venue}"
                    item['badge'] = f"SUB for {sub['absent_teacher']}" + (f" ({sub.get('absence_reason')})" if sub.get('absence_reason') else "")
                    item['badge_color'] = 'orange'
                    item['is_sub'] = True
                    item['request_id'] = sub['id']
                elif p_num and p_num in teaching_slots:
                    # Normal teaching
                    ts = teaching_slots[p_num]
                    venue = ts.get('venue_code') or 'TBC'
                    item['content'] = f"{ts.get('class_name', '')} {ts.get('subject', '')} • {venue}"
                else:
                    # Free period - check if room is occupied
                    if p_num and p_num in room_occupants:
                        item['content'] = room_occupants[p_num]
                        item['is_free_occupied'] = True
                        item['room_occupant'] = room_occupants[p_num]
                    else:
                        item['content'] = "Free"
                        item['is_free'] = True
            
            elif slot['slot_type'] == 'break':
                if terrain_duty:
                    item['content'] = f"Terrain: {terrain_duty['area_name']}"
                    item['badge'] = 'DUTY'
                    item['badge_color'] = 'blue'
                    item['is_duty'] = True
                else:
                    item['content'] = "Break"
            
            elif slot['slot_type'] == 'study':
                if homework_duty:
                    item['content'] = "Homework Venue"
                    item['badge'] = 'DUTY'
                    item['badge_color'] = 'purple'
                    item['is_duty'] = True
                else:
                    item['content'] = slot['slot_name']
            
            else:
                item['content'] = slot['slot_name']
            
            schedule.append(item)
    
    sub_count = len(sub_assignments)
    duty_count = (1 if terrain_duty else 0) + (1 if homework_duty else 0)
    sport_count = len(sport_duties)
    
    if viewing_other:
        nav_header = get_nav_header("My Day", "/timetables/", "Back")
    else:
        nav_header = get_nav_header("My Day", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('duty/my_day.html',
                          schedule=schedule,
                          display_date=target_date.strftime('%A, %d %b'),
                          day_name=day_name,
                          day_type=day_type,
                          cycle_day=cycle_day,
                          sub_count=sub_count,
                          duty_count=duty_count,
                          sport_count=sport_count,
                          terrain_duty=terrain_duty,
                          homework_duty=homework_duty,
                          sport_duties=sport_duties,
                          nav_header=nav_header,
                          nav_styles=nav_styles,
                          current_tab=tab,
                          school_days=school_days,
                          is_absent=is_absent,
                          absence_type=absence_type,
                          viewing_other=viewing_other,
                          viewing_name=viewing_name)


@duty_bp.route('/terrain')
@duty_bp.route('/terrain')
def terrain_roster():
    """Weekly terrain duty roster - shows all staff assignments."""
    staff_id = session.get('staff_id')
    week_param = request.args.get('week', 'current')  # 'current' or 'next'
    
    # Get current week (Mon-Fri)
    today = date.today()
    weekday = today.weekday()
    
    # Find Monday of current week
    if weekday == 5:  # Saturday
        this_monday = today + timedelta(days=2)
    elif weekday == 6:  # Sunday
        this_monday = today + timedelta(days=1)
    else:
        this_monday = today - timedelta(days=weekday)
    
    # Select which week to show
    if week_param == 'next':
        monday = this_monday + timedelta(days=7)
    else:
        monday = this_monday
    
    # Build list of 5 weekdays
    week_days = []
    for i in range(5):
        d = monday + timedelta(days=i)
        week_days.append({
            'date': d,
            'date_str': d.isoformat(),
            'day_name': d.strftime('%a'),
            'day_num': d.strftime('%d'),
            'is_today': d == today
        })
    
    week_start = monday.isoformat()
    week_end = (monday + timedelta(days=4)).isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get terrain areas (excluding Homework Venue for now)
        cursor.execute("""
            SELECT id, area_code, area_name
            FROM terrain_area
            WHERE tenant_id = ? AND is_active = 1 AND area_name NOT LIKE '%Homework%'
            ORDER BY sort_order
        """, (TENANT_ID,))
        areas = [dict(row) for row in cursor.fetchall()]
        
        # Get all terrain duties for the week
        cursor.execute("""
            SELECT dr.duty_date, dr.terrain_area_id, dr.staff_id, s.display_name
            FROM duty_roster dr
            JOIN staff s ON dr.staff_id = s.id
            WHERE dr.tenant_id = ? 
              AND dr.duty_type = 'terrain'
              AND dr.duty_date >= ? AND dr.duty_date <= ?
        """, (TENANT_ID, week_start, week_end))
        
        # Build lookup: {(area_id, date_str): {'staff_id': x, 'name': y}}
        terrain_duties = {}
        for row in cursor.fetchall():
            key = (row['terrain_area_id'], row['duty_date'])
            terrain_duties[key] = {
                'staff_id': row['staff_id'],
                'name': row['display_name']
            }
        
        # Get homework duties for the week
        cursor.execute("""
            SELECT dr.duty_date, dr.staff_id, s.display_name
            FROM duty_roster dr
            JOIN staff s ON dr.staff_id = s.id
            WHERE dr.tenant_id = ?
              AND dr.duty_type = 'homework'
              AND dr.duty_date >= ? AND dr.duty_date <= ?
        """, (TENANT_ID, week_start, week_end))
        
        homework_duties = {}
        for row in cursor.fetchall():
            homework_duties[row['duty_date']] = {
                'staff_id': row['staff_id'],
                'name': row['display_name']
            }
        
        # Get break times for display (use type_a as reference)
        cursor.execute("""
            SELECT slot_name, start_time, end_time
            FROM bell_schedule
            WHERE tenant_id = ? AND schedule_type = 'type_a' AND is_break = 1
            ORDER BY sort_order
        """, (TENANT_ID,))
        breaks = [dict(row) for row in cursor.fetchall()]
    
    # Build grid data for terrain areas
    grid = []
    for area in areas:
        row = {
            'area_id': area['id'],
            'area_name': area['area_name'],
            'area_code': area['area_code'],
            'days': []
        }
        for day in week_days:
            key = (area['id'], day['date_str'])
            duty = terrain_duties.get(key)
            row['days'].append({
                'date_str': day['date_str'],
                'staff_id': duty['staff_id'] if duty else None,
                'name': duty['name'] if duty else '—',
                'is_current_user': duty['staff_id'] == staff_id if duty else False
            })
        grid.append(row)
    
    # Add Homework Venue as last row (Mon-Thu only, Fri shows —)
    homework_row = {
        'area_id': 'homework',
        'area_name': 'Homework Venue',
        'area_code': 'HWV',
        'days': []
    }
    for i, day in enumerate(week_days):
        if i < 4:  # Mon-Thu
            duty = homework_duties.get(day['date_str'])
            homework_row['days'].append({
                'date_str': day['date_str'],
                'staff_id': duty['staff_id'] if duty else None,
                'name': duty['name'] if duty else '—',
                'is_current_user': duty['staff_id'] == staff_id if duty else False
            })
        else:  # Friday - no homework venue
            homework_row['days'].append({
                'date_str': day['date_str'],
                'staff_id': None,
                'name': '—',
                'is_current_user': False
            })
    grid.append(homework_row)
    
    nav_header = get_nav_header("Terrain Roster", "/", "Home")
    nav_styles = get_nav_styles()
    
    # Week label
    week_label = f"{monday.strftime('%d %b')} – {(monday + timedelta(days=4)).strftime('%d %b %Y')}"
    
    return render_template('duty/terrain.html',
                          grid=grid,
                          week_days=week_days,
                          breaks=breaks,
                          week_label=week_label,
                          week_param=week_param,
                          nav_header=nav_header,
                          nav_styles=nav_styles)

@duty_bp.route('/terrain/decline/<duty_id>', methods=['POST'])
def decline_terrain_duty(duty_id):
    """Decline a terrain duty assignment with auto-reassign."""
    import uuid
    from datetime import datetime, date, time
    
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    reason = request.form.get('reason', '').strip()
    return_to = request.form.get('return_to', '/duty/my-day')
    
    TENANT_ID = "MARAGON"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Verify this duty belongs to the current user
        cursor.execute("""
            SELECT dr.*, ta.area_name
            FROM duty_roster dr
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.id = ? AND dr.staff_id = ? AND dr.tenant_id = ?
        """, (duty_id, staff_id, TENANT_ID))
        duty = cursor.fetchone()
        
        if not duty:
            return redirect(return_to)
        
        # Check cutoff: can't decline after 06:30 on duty day
        duty_date = date.fromisoformat(duty['duty_date'])
        now = datetime.now()
        cutoff = datetime.combine(duty_date, time(6, 30))
        
        if now >= cutoff:
            # Too late to decline - redirect back with no action
            return redirect(return_to)
        
        # Get staff name for audit
        cursor.execute("SELECT display_name FROM staff WHERE id = ?", (staff_id,))
        staff_row = cursor.fetchone()
        staff_name = staff_row['display_name'] if staff_row else 'Unknown'
        
        # Log to duty_decline table
        decline_id = str(uuid.uuid4())
        duty_description = f"Terrain - {duty['area_name'] or duty['duty_type']}"
        cursor.execute("""
            INSERT INTO duty_decline (id, tenant_id, duty_type, staff_id, staff_name, duty_description, duty_date, reason)
            VALUES (?, ?, 'terrain', ?, ?, ?, ?, ?)
        """, (decline_id, TENANT_ID, staff_id, staff_name, duty_description, duty['duty_date'], reason or None))
        
        # Find replacement: next eligible staff alphabetically who isn't on terrain that day
        cursor.execute("""
            SELECT id, display_name, first_name
            FROM staff
            WHERE tenant_id = ? AND can_do_duty = 1 AND is_active = 1
              AND id NOT IN (
                  SELECT staff_id FROM duty_roster 
                  WHERE tenant_id = ? AND duty_date = ? AND duty_type = 'terrain'
              )
            ORDER BY first_name ASC, surname ASC
            LIMIT 1
        """, (TENANT_ID, TENANT_ID, duty['duty_date']))
        replacement = cursor.fetchone()
        
        if replacement:
            # Reassign to replacement
            cursor.execute("""
                UPDATE duty_roster 
                SET staff_id = ?
                WHERE id = ? AND tenant_id = ?
            """, (replacement['id'], duty_id, TENANT_ID))
        else:
            # No replacement available - delete the duty
            cursor.execute("DELETE FROM duty_roster WHERE id = ? AND tenant_id = ?", (duty_id, TENANT_ID))
        
        conn.commit()
    
    return redirect(return_to)
