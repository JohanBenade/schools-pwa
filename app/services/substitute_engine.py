"""
Substitute Allocation Engine
The magic that auto-assigns substitutes when a teacher reports sick.
Updated: Multi-day support
"""

import uuid
from datetime import datetime, date, timedelta
from app.services.db import get_connection

TENANT_ID = "MARAGON"


def get_cycle_day(target_date=None):
    """
    Calculate which cycle day (1-7) a given date is.
    Based on cycle_start_date in substitute_config.
    """
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT cycle_start_date, cycle_length 
            FROM substitute_config 
            WHERE tenant_id = ?
        """, (TENANT_ID,))
        row = cursor.fetchone()
        
        if not row or not row['cycle_start_date']:
            return 3  # Default to Day 3 for demo
        
        start_date = datetime.strptime(row['cycle_start_date'], '%Y-%m-%d').date()
        cycle_length = row['cycle_length'] or 7
        
        # Count weekdays between start and target
        days_diff = 0
        current = start_date
        while current < target_date:
            if current.weekday() < 5:  # Monday = 0, Friday = 4
                days_diff += 1
            current = datetime.fromordinal(current.toordinal() + 1).date()
        
        cycle_day = (days_diff % cycle_length) + 1
        return cycle_day


def get_weekdays_between(start_date, end_date):
    """Get list of weekdays (Mon-Fri) between start and end dates inclusive."""
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    weekdays = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            weekdays.append(current)
        current += timedelta(days=1)
    
    return weekdays


def get_teacher_schedule(staff_id, cycle_day):
    """Get a teacher's teaching periods for a specific cycle day."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, p.period_number, p.period_name, p.start_time, p.end_time,
                   v.venue_code, v.venue_name
            FROM timetable_slot t
            JOIN period p ON t.period_id = p.id
            LEFT JOIN venue v ON t.venue_id = v.id
            WHERE t.staff_id = ? AND t.cycle_day = ? AND t.tenant_id = ?
            ORDER BY p.sort_order
        """, (staff_id, cycle_day, TENANT_ID))
        return [dict(row) for row in cursor.fetchall()]


def get_free_teachers_for_period(period_id, cycle_day, exclude_staff_ids=None):
    """
    Find all teachers who are FREE during a specific period.
    Returns list sorted by surname (A-Z).
    """
    exclude_staff_ids = exclude_staff_ids or []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all teachers who CAN substitute
        cursor.execute("""
            SELECT id, surname, display_name, first_name 
            FROM staff 
            WHERE tenant_id = ? AND is_active = 1 AND can_substitute = 1
            ORDER BY first_name
        """, (TENANT_ID,))
        all_teachers = cursor.fetchall()
        
        # Get teachers who ARE teaching this period
        cursor.execute("""
            SELECT DISTINCT staff_id 
            FROM timetable_slot 
            WHERE tenant_id = ? AND cycle_day = ? AND period_id = ?
        """, (TENANT_ID, cycle_day, period_id))
        busy_teachers = {row['staff_id'] for row in cursor.fetchall()}
        
        # Free = can substitute AND not teaching AND not excluded
        free_teachers = []
        for teacher in all_teachers:
            if (teacher['id'] not in busy_teachers and 
                teacher['id'] not in exclude_staff_ids):
                free_teachers.append(dict(teacher))
        
        return free_teachers


def get_teachers_assigned_on_date(target_date):
    """Get list of staff_ids already assigned as substitute on a specific date."""
    if isinstance(target_date, date):
        target_date = target_date.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT substitute_id 
            FROM substitute_request 
            WHERE request_date = ? AND status IN ('Assigned', 'Confirmed') AND substitute_id IS NOT NULL
        """, (target_date,))
        return [row['substitute_id'] for row in cursor.fetchall()]


def get_next_substitute(period_id, cycle_day, already_assigned_today, pointer_surname):
    """
    Find the next substitute using A-Z rotation.
    - Get free teachers for this period
    - Exclude those already assigned today
    - Pick first one at or after pointer_surname
    - If none found after pointer, wrap to 'A'
    """
    free_teachers = get_free_teachers_for_period(
        period_id, cycle_day, exclude_staff_ids=already_assigned_today
    )
    
    if not free_teachers:
        return None, pointer_surname
    
    # Find first teacher at or after pointer
    for teacher in free_teachers:
        if teacher['first_name'].upper() >= pointer_surname.upper():
            # Move pointer to next letter after this surname
            name_part = teacher['display_name'].split(' ')[-1] if teacher['display_name'] else 'A'
            next_pointer = name_part[0].upper()
            if next_pointer < 'Z':
                next_pointer = chr(ord(next_pointer) + 1)
            else:
                next_pointer = 'A'
            return teacher, next_pointer
    
    # Wrap around - pick first in list
    teacher = free_teachers[0]
    name_part = teacher["first_name"] if teacher["display_name"] else "A"
    next_pointer = name_part[0].upper()
    if next_pointer < 'Z':
        next_pointer = chr(ord(next_pointer) + 1)
    else:
        next_pointer = 'A'
    return teacher, next_pointer


def get_adjacent_teacher(venue_code):
    """
    Find teacher in adjacent classroom for mentor roll call.
    Returns first teacher found in adjacent room.
    """
    if not venue_code or len(venue_code) < 4:
        return None
    
    block = venue_code[0]
    try:
        room_num = int(venue_code[1:])
    except ValueError:
        return None
    
    # Check adjacent rooms in order: +1, -1, +2, -2
    adjacent_offsets = [1, -1, 2, -2]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for offset in adjacent_offsets:
            adj_num = room_num + offset
            if adj_num <= 0:
                continue
            
            adj_code = f"{block}{adj_num:03d}"
            
            # Find teacher assigned to this room
            cursor.execute("""
                SELECT s.id, s.display_name, s.surname, v.venue_code
                FROM staff_venue sv
                JOIN staff s ON sv.staff_id = s.id
                JOIN venue v ON sv.venue_id = v.id
                WHERE v.venue_code = ? AND v.tenant_id = ? AND s.is_active = 1
            """, (adj_code, TENANT_ID))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
    
    return None


def log_event(absence_id, event_type, staff_id=None, details=None, substitute_request_id=None):
    """Log an event to substitute_log for Mission Control."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO substitute_log 
            (id, tenant_id, absence_id, substitute_request_id, event_type, staff_id, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), TENANT_ID, absence_id, substitute_request_id, 
              event_type, staff_id, details, datetime.now().isoformat()))
        conn.commit()


def update_pointer(new_pointer):
    """Update the A-Z rotation pointer."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE substitute_config 
            SET pointer_surname = ?, pointer_updated_at = ?, updated_at = ?
            WHERE tenant_id = ?
        """, (new_pointer, datetime.now().isoformat(), datetime.now().isoformat(), TENANT_ID))
        conn.commit()


def get_current_pointer():
    """Get current A-Z pointer position."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pointer_surname FROM substitute_config WHERE tenant_id = ?
        """, (TENANT_ID,))
        row = cursor.fetchone()
        return row['pointer_surname'] if row else 'A'


def process_absence(absence_id):
    """
    Main allocation engine - process a reported absence.
    UPDATED: Supports multi-day absences.
    
    1. Get absence date range (start_date to end_date)
    2. For each weekday in range:
       a. Get sick teacher's schedule for that cycle day
       b. Check if mentor teacher - assign roll call
       c. For each teaching period, find and assign substitute
    3. Log everything for Mission Control
    4. Return results for display
    
    Returns dict with allocation results.
    """
    results = {
        'absence_id': absence_id,
        'started_at': datetime.now().isoformat(),
        'days': [],
        'pointer_start': get_current_pointer(),
        'pointer_end': None,
        'success': False
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get absence details
        cursor.execute("""
            SELECT a.*, s.display_name, s.surname, sv.venue_id, v.venue_code,
                   mg.id as mentor_group_id, mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN staff_venue sv ON s.id = sv.staff_id
            LEFT JOIN venue v ON sv.venue_id = v.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.id = ?
        """, (absence_id,))
        
        absence = cursor.fetchone()
        if not absence:
            results['error'] = 'Absence not found'
            return results
        
        absence = dict(absence)
        results['sick_teacher'] = {
            'name': absence['display_name'],
            'venue': absence['venue_code'],
            'mentor_class': absence['mentor_class']
        }
        
        # Log start
        log_event(absence_id, 'processing_started')
        
        # Determine date range
        start_date = absence['absence_date']
        end_date = absence.get('end_date') or start_date  # Single day if no end_date
        
        # Get all weekdays in range
        weekdays = get_weekdays_between(start_date, end_date)
        results['date_range'] = {
            'start': start_date,
            'end': end_date,
            'total_days': len(weekdays)
        }
        
        pointer = get_current_pointer()
        total_covered = 0
        total_periods = 0
        
        # Process each day
        for target_date in weekdays:
            target_date_str = target_date.isoformat()
            day_result = {
                'date': target_date_str,
                'date_display': target_date.strftime('%a %d %b'),
                'cycle_day': get_cycle_day(target_date),
                'roll_call': None,
                'periods': []
            }
            
            cycle_day = day_result['cycle_day']
            
            # Get teachers already assigned on this specific date
            already_assigned_today = get_teachers_assigned_on_date(target_date)
            
            # === MENTOR ROLL CALL (only first day for simplicity) ===
            if absence['mentor_group_id']:
                adjacent_teacher = get_adjacent_teacher(absence['venue_code'])
                
                if adjacent_teacher:
                    request_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO substitute_request
                        (id, tenant_id, absence_id, period_id, substitute_id, status,
                         is_mentor_duty, mentor_group_id, class_name, venue_name, assigned_at, request_date)
                        VALUES (?, ?, ?, ?, ?, 'Assigned', 1, ?, ?, ?, ?, ?)
                    """, (request_id, TENANT_ID, absence_id, None, adjacent_teacher['id'],
                          absence['mentor_group_id'], absence['mentor_class'],
                          absence['venue_code'], datetime.now().isoformat(), target_date_str))
                    conn.commit()
                    
                    log_event(absence_id, 'allocated', adjacent_teacher['id'],
                             f"[{target_date_str}] Mentor roll call {absence['mentor_class']} - adjacent room {adjacent_teacher['venue_code']}",
                             request_id)
                    
                    day_result['roll_call'] = {
                        'substitute': adjacent_teacher['display_name'],
                        'venue': adjacent_teacher['venue_code'],
                        'mentor_class': absence['mentor_class'],
                        'request_id': request_id
                    }
                else:
                    log_event(absence_id, 'no_cover', None, 
                             f"[{target_date_str}] No adjacent teacher for mentor roll call {absence['mentor_class']}")
                    day_result['roll_call'] = {'error': 'No adjacent teacher found'}
            
            # === TEACHING PERIODS ===
            schedule = get_teacher_schedule(absence['staff_id'], cycle_day)
            
            for slot in schedule:
                period_result = {
                    'period_name': slot['period_name'],
                    'period_number': slot['period_number'],
                    'class_name': slot['class_name'],
                    'subject': slot['subject'],
                    'venue': slot['venue_code'],
                    'substitute': None,
                    'status': None
                }
                
                total_periods += 1
                
                # Find substitute
                sub_teacher, new_pointer = get_next_substitute(
                    slot['period_id'], cycle_day, already_assigned_today, pointer
                )
                
                if sub_teacher:
                    request_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO substitute_request
                        (id, tenant_id, absence_id, period_id, substitute_id, status,
                         class_name, subject, venue_id, venue_name, assigned_at, request_date)
                        VALUES (?, ?, ?, ?, ?, 'Assigned', ?, ?, ?, ?, ?, ?)
                    """, (request_id, TENANT_ID, absence_id, slot['period_id'],
                          sub_teacher['id'], slot['class_name'], slot['subject'],
                          slot['venue_id'], slot['venue_code'], datetime.now().isoformat(),
                          target_date_str))
                    conn.commit()
                    
                    log_event(absence_id, 'allocated', sub_teacher['id'],
                             f"[{target_date_str}] {slot['period_name']}: {slot['class_name']} in {slot['venue_code']}",
                             request_id)
                    
                    period_result['substitute'] = sub_teacher['display_name']
                    period_result['substitute_id'] = sub_teacher['id']
                    period_result['request_id'] = request_id
                    period_result['status'] = 'assigned'
                    
                    already_assigned_today.append(sub_teacher['id'])
                    total_covered += 1
                    pointer = new_pointer
                    
                else:
                    log_event(absence_id, 'no_cover', None,
                             f"[{target_date_str}] {slot['period_name']}: No substitute available")
                    period_result['status'] = 'no_cover'
                
                day_result['periods'].append(period_result)
            
            results['days'].append(day_result)
        
        # Update pointer
        update_pointer(pointer)
        results['pointer_end'] = pointer
        
        # Update absence status
        if total_covered == total_periods:
            new_status = 'Covered'
        elif total_covered > 0:
            new_status = 'Partial'
        else:
            new_status = 'Escalated'
        
        cursor.execute("""
            UPDATE absence SET status = ?, updated_at = ? WHERE id = ?
        """, (new_status, datetime.now().isoformat(), absence_id))
        conn.commit()
        
        results['absence_status'] = new_status
        results['covered_count'] = total_covered
        results['total_count'] = total_periods
        
        # Log completion
        log_event(absence_id, 'processing_complete', None,
                 f"Covered {total_covered}/{total_periods} periods over {len(weekdays)} days. Pointer: {results['pointer_start']} -> {pointer}")
        
        results['completed_at'] = datetime.now().isoformat()
        results['success'] = True
        
    return results


def create_absence(staff_id, absence_date, absence_type, reason, is_full_day=True,
                   start_period=None, end_period=None, reported_by_id=None):
    """
    Create a new absence record (single day - legacy support).
    Returns absence_id.
    """
    absence_id = str(uuid.uuid4())
    reported_by = reported_by_id or staff_id
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO absence
            (id, tenant_id, staff_id, absence_date, absence_type, reason,
             is_full_day, start_period_id, end_period_id, reported_by_id, reported_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Reported')
        """, (absence_id, TENANT_ID, staff_id, absence_date, absence_type, reason,
              1 if is_full_day else 0, start_period, end_period, reported_by,
              datetime.now().isoformat()))
        conn.commit()
    
    log_event(absence_id, 'absence_reported', staff_id, 
             f"{absence_type}: {reason or 'No reason given'}")
    
    return absence_id


def reassign_declined_request(request_id, declined_by_id):
    """Reassign a declined substitute request to next available teacher."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get the declined request details
        cursor.execute("""
            SELECT sr.*, a.staff_id as absent_staff_id, a.id as absence_id
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            WHERE sr.id = ?
        """, (request_id,))
        req = cursor.fetchone()
        if not req:
            return None
        req = dict(req)
        
        target_date = req['request_date']
        
        # Get teachers already assigned on this date (excluding the decliner who's now free again)
        assigned_today = get_teachers_assigned_on_date(target_date)
        assigned_today = set(assigned_today); assigned_today.discard(declined_by_id)  # Decliner is available again
        
        # Get cycle day for this date
        cursor.execute("SELECT cycle_day FROM cycle_day_config WHERE calendar_date = ? AND tenant_id = ?",
                      (target_date, TENANT_ID))
        cycle_row = cursor.fetchone()
        cycle_day = cycle_row['cycle_day'] if cycle_row else 1
        
        # Get current pointer
        cursor.execute("SELECT pointer_surname FROM substitute_config WHERE tenant_id = ?", (TENANT_ID,))
        config = cursor.fetchone()
        pointer = config['pointer_surname'] if config else 'A'
        
        # Get available teachers for this period (free this period, not absent, not the decliner)
        if req['period_id']:
            cursor.execute("""
                SELECT s.id, s.surname, s.display_name
                FROM staff s
                WHERE s.tenant_id = ?
                  AND s.is_active = 1
                  AND s.can_substitute = 1
                  AND s.id != ?
                  AND s.id != ?
                  AND s.id NOT IN (
                      SELECT staff_id FROM absence 
                      WHERE absence_date <= ? AND COALESCE(end_date, absence_date) >= ?
                        AND status != 'Cancelled'
                  )
                  AND s.id NOT IN (
                      SELECT staff_id FROM timetable_slot 
                      WHERE period_id = ? AND cycle_day = ?
                  )
                ORDER BY 
                    CASE WHEN s.surname >= ? THEN 0 ELSE 1 END,
                    s.surname
            """, (TENANT_ID, req['absent_staff_id'], declined_by_id, target_date, target_date,
                  req['period_id'], cycle_day, pointer))
        else:
            # Mentor duty - find adjacent room teacher or any available
            cursor.execute("""
                SELECT s.id, s.surname, s.display_name
                FROM staff s
                WHERE s.tenant_id = ?
                  AND s.is_active = 1
                  AND s.can_substitute = 1
                  AND s.id != ?
                  AND s.id != ?
                ORDER BY 
                    CASE WHEN s.surname >= ? THEN 0 ELSE 1 END,
                    s.surname
            """, (TENANT_ID, req['absent_staff_id'], declined_by_id, pointer))
        
        candidates = [dict(row) for row in cursor.fetchall()]
        
        # Pass 1: Teachers with 0 subs today
        new_sub = None
        for c in candidates:
            if c['id'] not in assigned_today:
                new_sub = c
                break
        
        # Pass 2: Teachers with 1 sub today
        if not new_sub:
            for c in candidates:
                new_sub = c
                break
        
        if new_sub:
            # Update the request with new substitute
            cursor.execute("""
                UPDATE substitute_request
                SET substitute_id = ?, status = 'Assigned', 
                    declined_at = NULL, declined_by_id = NULL, decline_reason = NULL
            WHERE id = ?
            """, (new_sub['id'], request_id))
            
            # Log the reassignment
            cursor.execute("""
                INSERT INTO substitute_log (id, absence_id, event_type, details, staff_id, tenant_id, created_at)
                VALUES (?, ?, 'reassigned', ?, ?, ?, ?)
            """, (str(uuid.uuid4()), req['absence_id'],
                  f"Reassigned to {new_sub['display_name']}",
                  new_sub['id'], TENANT_ID, datetime.now().isoformat()))
            
            conn.commit()
            return new_sub
        else:
            # No one available - mark as escalated
            cursor.execute("""
                UPDATE substitute_request SET status = 'Escalated' WHERE id = ?
            """, (request_id,))
            
            cursor.execute("""
                INSERT INTO substitute_log (id, absence_id, event_type, details, staff_id, tenant_id, created_at)
                VALUES (?, ?, 'no_cover', ?, NULL, ?, ?)
            """, (str(uuid.uuid4()), req['absence_id'],
                  f"No substitute available after decline",
                  TENANT_ID, datetime.now().isoformat()))
            
            conn.commit()
            return None
