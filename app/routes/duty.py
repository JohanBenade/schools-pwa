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


@duty_bp.route('/my-day')
def my_day():
    """Teacher's full daily schedule view."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    
    tab = request.args.get('tab', 'today')
    today_date = date.today()
    tomorrow_date = today_date + timedelta(days=1)
    
    if tab == 'tomorrow':
        target_date = tomorrow_date
    else:
        target_date = today_date
    
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
                'content': f"{sport['duty_type']}: {sport['duty_role'] or 'Assigned'}",
                'badge': sport['sport_type'],
                'badge_color': 'teal',
                'is_duty': False,
                'is_sub': False,
                'is_free': False,
                'is_sport': True,
                'request_id': None,
                'event_id': sport['event_id'],
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
                'is_sport': False,
                'request_id': None
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
                'is_sport': False,
                'request_id': None
            }
            
            if slot['slot_type'] == 'register':
                if mentor_sub:
                    item['content'] = f"Covering for {mentor_sub['absent_teacher']}"
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
                    sub = sub_by_period[p_num]
                    venue = sub.get('venue_name') or 'TBC'
                    item['content'] = f"{sub.get('class_name', '')} {sub.get('subject', '')} • {venue}"
                    item['badge'] = f"SUB for {sub['absent_teacher']}" + (f" ({sub.get('absence_reason')})" if sub.get('absence_reason') else "")
                    item['badge_color'] = 'orange'
                    item['is_sub'] = True
                    item['request_id'] = sub['id']
                elif p_num and p_num in teaching_slots:
                    ts = teaching_slots[p_num]
                    venue = ts.get('venue_code') or 'TBC'
                    item['content'] = f"{ts.get('class_name', '')} {ts.get('subject', '')} • {venue}"
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
                          current_tab=tab,                          is_absent=is_absent,                          absence_type=absence_type)
