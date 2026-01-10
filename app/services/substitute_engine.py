"""
Substitute Allocation Engine
The magic that auto-assigns substitutes when a teacher reports sick.
"""

import uuid
from datetime import datetime, date
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
            SELECT id, surname, display_name 
            FROM staff 
            WHERE tenant_id = ? AND is_active = 1 AND can_substitute = 1
            ORDER BY surname
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
        if teacher['surname'].upper() >= pointer_surname.upper():
            # Move pointer to next letter after this surname
            next_pointer = teacher['surname'][0].upper()
            if next_pointer < 'Z':
                next_pointer = chr(ord(next_pointer) + 1)
            else:
                next_pointer = 'A'
            return teacher, next_pointer
    
    # Wrap around - pick first in list
    teacher = free_teachers[0]
    next_pointer = teacher['surname'][0].upper()
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
    
    1. Get sick teacher's schedule for today
    2. Check if mentor teacher - assign roll call to adjacent teacher
    3. For each teaching period, find and assign substitute
    4. Log everything for Mission Control
    5. Return results for display
    
    Returns dict with allocation results.
    """
    results = {
        'absence_id': absence_id,
        'started_at': datetime.now().isoformat(),
        'roll_call': None,
        'periods': [],
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
        
        # Get cycle day
        cycle_day = get_cycle_day(absence['absence_date'])
        results['cycle_day'] = cycle_day
        
        # === MENTOR ROLL CALL ===
        if absence['mentor_group_id']:
            adjacent_teacher = get_adjacent_teacher(absence['venue_code'])
            
            if adjacent_teacher:
                # Create roll call assignment
                request_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO substitute_request
                    (id, tenant_id, absence_id, period_id, substitute_id, status,
                     is_mentor_duty, mentor_group_id, class_name, venue_name, assigned_at)
                    VALUES (?, ?, ?, ?, ?, 'Assigned', 1, ?, ?, ?, ?)
                """, (request_id, TENANT_ID, absence_id, None, adjacent_teacher['id'],
                      absence['mentor_group_id'], absence['mentor_class'],
                      absence['venue_code'], datetime.now().isoformat()))
                conn.commit()
                
                log_event(absence_id, 'allocated', adjacent_teacher['id'],
                         f"Mentor roll call {absence['mentor_class']} - adjacent room {adjacent_teacher['venue_code']}",
                         request_id)
                
                results['roll_call'] = {
                    'substitute': adjacent_teacher['display_name'],
                    'venue': adjacent_teacher['venue_code'],
                    'mentor_class': absence['mentor_class'],
                    'request_id': request_id
                }
            else:
                log_event(absence_id, 'no_cover', None, 
                         f"No adjacent teacher for mentor roll call {absence['mentor_class']}")
                results['roll_call'] = {'error': 'No adjacent teacher found'}
        
        # === TEACHING PERIODS ===
        schedule = get_teacher_schedule(absence['staff_id'], cycle_day)
        
        # Filter by start/end period if partial day
        # (For now, process all - can filter later)
        
        pointer = get_current_pointer()
        already_assigned_today = []
        
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
            
            # Find substitute
            sub_teacher, new_pointer = get_next_substitute(
                slot['period_id'], cycle_day, already_assigned_today, pointer
            )
            
            if sub_teacher:
                # Create substitute request
                request_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO substitute_request
                    (id, tenant_id, absence_id, period_id, substitute_id, status,
                     class_name, subject, venue_id, venue_name, assigned_at)
                    VALUES (?, ?, ?, ?, ?, 'Assigned', ?, ?, ?, ?, ?)
                """, (request_id, TENANT_ID, absence_id, slot['period_id'],
                      sub_teacher['id'], slot['class_name'], slot['subject'],
                      slot['venue_id'], slot['venue_code'], datetime.now().isoformat()))
                conn.commit()
                
                log_event(absence_id, 'allocated', sub_teacher['id'],
                         f"{slot['period_name']}: {slot['class_name']} in {slot['venue_code']}",
                         request_id)
                
                period_result['substitute'] = sub_teacher['display_name']
                period_result['substitute_id'] = sub_teacher['id']
                period_result['request_id'] = request_id
                period_result['status'] = 'assigned'
                
                # Track for one-sub-per-day rule
                already_assigned_today.append(sub_teacher['id'])
                pointer = new_pointer
                
            else:
                # No cover available
                log_event(absence_id, 'no_cover', None,
                         f"{slot['period_name']}: No substitute available")
                period_result['status'] = 'no_cover'
            
            results['periods'].append(period_result)
        
        # Update pointer
        update_pointer(pointer)
        results['pointer_end'] = pointer
        
        # Update absence status
        covered_count = sum(1 for p in results['periods'] if p['status'] == 'assigned')
        total_count = len(results['periods'])
        
        if covered_count == total_count:
            new_status = 'Covered'
        elif covered_count > 0:
            new_status = 'Partial'
        else:
            new_status = 'Escalated'
        
        cursor.execute("""
            UPDATE absence SET status = ?, updated_at = ? WHERE id = ?
        """, (new_status, datetime.now().isoformat(), absence_id))
        conn.commit()
        
        results['absence_status'] = new_status
        results['covered_count'] = covered_count
        results['total_count'] = total_count
        
        # Log completion
        log_event(absence_id, 'processing_complete', None,
                 f"Covered {covered_count}/{total_count} periods. Pointer: {results['pointer_start']} -> {pointer}")
        
        results['completed_at'] = datetime.now().isoformat()
        results['success'] = True
        
    return results


def create_absence(staff_id, absence_date, absence_type, reason, is_full_day=True,
                   start_period=None, end_period=None, reported_by_id=None):
    """
    Create a new absence record.
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
