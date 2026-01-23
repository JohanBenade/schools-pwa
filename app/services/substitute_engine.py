"""
Substitute Allocation Engine
The magic that auto-assigns substitutes when a teacher reports sick.
Updated: Multi-day support + absence checking
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


def get_absent_staff_on_date(target_date):
    """Get list of staff_ids who are absent on a specific date."""
    if isinstance(target_date, date):
        target_date_str = target_date.isoformat()
    else:
        target_date_str = target_date
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT staff_id 
            FROM absence 
            WHERE absence_date <= ? 
              AND COALESCE(end_date, absence_date) >= ?
              AND status != 'Cancelled'
        """, (target_date_str, target_date_str))
        return [row['staff_id'] for row in cursor.fetchall()]


def get_free_teachers_for_period(period_id, cycle_day, exclude_staff_ids=None, target_date=None):
    """
    Find all teachers who are FREE during a specific period.
    Now includes:
    - Room blocking: if teacher's home room is occupied, they can't sub
    - Absence checking: teachers who are out sick are excluded
    Returns list sorted by first name (A-Z).
    """
    exclude_staff_ids = exclude_staff_ids or []
    
    # Get absent staff for this date
    if target_date is None:
        target_date = date.today()
    absent_staff = get_absent_staff_on_date(target_date)
    
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
        
        # Get home room assignments (staff_id -> venue_id)
        cursor.execute("""
            SELECT staff_id, venue_id FROM staff_venue WHERE tenant_id = ?
        """, (TENANT_ID,))
        home_rooms = {row['staff_id']: row['venue_id'] for row in cursor.fetchall()}
        
        # Get rooms occupied by OTHER teachers this period
        cursor.execute("""
            SELECT DISTINCT venue_id 
            FROM timetable_slot 
            WHERE tenant_id = ? AND cycle_day = ? AND period_id = ? AND venue_id IS NOT NULL
        """, (TENANT_ID, cycle_day, period_id))
        occupied_rooms = {row['venue_id'] for row in cursor.fetchall()}
        
        # Free = can substitute AND not teaching AND not excluded AND not absent AND room not blocked
        free_teachers = []
        for teacher in all_teachers:
            teacher_id = teacher['id']
            
            # Skip if teaching
            if teacher_id in busy_teachers:
                continue
            
            # Skip if explicitly excluded
            if teacher_id in exclude_staff_ids:
                continue
            
            # Skip if absent/sick
            if teacher_id in absent_staff:
                continue
            
            # Check room blocking (only for teachers with home rooms)
            home_room = home_rooms.get(teacher_id)
            if home_room and home_room in occupied_rooms:
                # Teacher's home room is occupied by someone else - can't sub
                continue
            
            # Floaters (no home room) or room is free - available!
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


def get_next_substitute(period_id, cycle_day, already_assigned_today, pointer_surname, target_date=None):
    """
    Find the next substitute using A-Z rotation.
    - Get free teachers for this period
    - Exclude those already assigned today
    - Pick first one at or after pointer_surname
    - If none found after pointer, wrap to 'A'
    """
    free_teachers = get_free_teachers_for_period(
        period_id, cycle_day, exclude_staff_ids=already_assigned_today, target_date=target_date
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


# Room proximity map based on Maragon building layout
# Each room maps to an ordered list of nearest rooms
ROOM_PROXIMITY = {
    # Ground Floor Row 1 (facing Peace Park)
    'A005': ['A004', 'A006', 'A003', 'A007', 'A008'],
    'A004': ['A005', 'A003', 'A006', 'A002', 'A007'],
    'A003': ['A004', 'A002', 'A005', 'A001', 'A006'],
    'A002': ['A003', 'A001', 'A004', 'B001', 'A005'],
    'A001': ['A002', 'B001', 'A003', 'B002', 'A004'],
    'B001': ['A001', 'B002', 'A002', 'B003', 'A003'],
    'B002': ['B001', 'B003', 'A001', 'A002'],
    'B003': ['B002', 'B001', 'A001'],
    
    # Ground Floor Row 2 (vertical near A005)
    'A006': ['A005', 'A007', 'A004', 'A003', 'A008'],
    'A007': ['A006', 'A005', 'A008', 'A004', 'A009'],
    
    # Ground Floor Row 3
    'A008': ['A007', 'A009', 'A006', 'A010', 'A005'],
    'A009': ['A008', 'A010', 'A007', 'A011', 'A006'],
    'A010': ['A009', 'A011', 'A008', 'A012', 'A007'],
    'A011': ['A010', 'A012', 'A009', 'A008'],
    'A012': ['A011', 'A010', 'A009'],
    
    # First Floor Row 1
    'A105': ['A104', 'A106', 'A103', 'A107', 'A005'],
    'A104': ['A105', 'A103', 'A106', 'A102', 'A004'],
    'A103': ['A104', 'A102', 'A105', 'A101', 'A003'],
    'A102': ['A103', 'A101', 'A104', 'B101', 'A002'],
    'A101': ['A102', 'B101', 'A103', 'B102', 'A001'],
    'B101': ['A101', 'B102', 'A102', 'B103', 'B001'],
    'B102': ['B101', 'B103', 'A101', 'B001', 'B002'],
    'B103': ['B102', 'B101', 'A101', 'B003'],
    
    # First Floor Row 2 (corner)
    'A106': ['A105', 'A107', 'A104', 'A108', 'A006'],
    
    # First Floor Row 3
    'A107': ['A106', 'A108', 'A105', 'A109', 'A007'],
    'A108': ['A107', 'A109', 'A106', 'A110', 'A008'],
    'A109': ['A108', 'A110', 'A107', 'A111', 'A009'],
    'A110': ['A109', 'A111', 'A108', 'A112', 'A010'],
    'A111': ['A110', 'A112', 'A109', 'A108'],
    'A112': ['A111', 'A110', 'A109'],
    
    # Admin Block / CAT venue
    'A113': ['A118', 'A112', 'A111'],
    
    # Staffroom Wing
    'A118': ['A119', 'A113', 'A120'],
    'A119': ['A118', 'A120', 'A113', 'A121'],
    'A120': ['A119', 'A121', 'A118', 'A113'],
    'A121': ['A120', 'A119', 'A118'],
}


def get_adjacent_teacher(venue_code):
    """
    Find teacher in nearest classroom for mentor roll call.
    Uses building layout proximity map for accurate neighbor detection.
    Returns first available teacher found in nearby rooms (ordered by proximity).
    """
    if not venue_code:
        return None
    
    # Normalize venue code (uppercase)
    venue_code = venue_code.upper()
    
    # Get ordered list of nearby rooms
    nearby_rooms = ROOM_PROXIMITY.get(venue_code, [])
    
    if not nearby_rooms:
        # Fallback for unmapped rooms: try simple +1/-1 logic
        if len(venue_code) >= 4:
            block = venue_code[0]
            try:
                room_num = int(venue_code[1:])
                nearby_rooms = [f"{block}{room_num + 1:03d}", f"{block}{room_num - 1:03d}"]
            except ValueError:
                return None
        else:
            return None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for adj_code in nearby_rooms:
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
            
            # === MENTOR ROLL CALL ===
            if absence['mentor_group_id']:
                # New logic: Grade Backup -> Grade Head -> No Cover
                cover = get_mentor_register_cover(absence['mentor_group_id'], target_date)
                
                if cover:
                    request_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO substitute_request
                        (id, tenant_id, absence_id, period_id, substitute_id, status,
                         is_mentor_duty, mentor_group_id, class_name, venue_name, assigned_at, request_date)
                        VALUES (?, ?, ?, ?, ?, 'Assigned', 1, ?, ?, ?, ?, ?)
                    """, (request_id, TENANT_ID, absence_id, None, cover['staff_id'],
                          absence['mentor_group_id'], absence['mentor_class'],
                          absence['venue_code'], datetime.now().isoformat(), target_date_str))
                    conn.commit()
                    
                    fallback_note = f" ({cover['fallback_level']})" if cover['fallback_level'] == 'grade_head' else ""
                    log_event(absence_id, 'allocated', cover['staff_id'],
                             f"[{target_date_str}] Mentor register {absence['mentor_class']} -> {cover['display_name']}{fallback_note}",
                             request_id)
                    
                    day_result['roll_call'] = {
                        'substitute': cover['display_name'],
                        'venue': absence['venue_code'],
                        'mentor_class': absence['mentor_class'],
                        'request_id': request_id,
                        'fallback_level': cover['fallback_level']
                    }
                else:
                    # No cover available - create Pending request for manual assignment
                    request_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO substitute_request
                        (id, tenant_id, absence_id, period_id, substitute_id, status,
                         is_mentor_duty, mentor_group_id, class_name, venue_name, request_date)
                        VALUES (?, ?, ?, ?, NULL, 'Pending', 1, ?, ?, ?, ?)
                    """, (request_id, TENANT_ID, absence_id, None,
                          absence['mentor_group_id'], absence['mentor_class'],
                          absence['venue_code'], target_date_str))
                    conn.commit()
                    
                    log_event(absence_id, 'no_cover', None,
                             f"[{target_date_str}] Mentor register {absence['mentor_class']} - no cover (backup & head absent)",
                             request_id)
                    
                    day_result['roll_call'] = {
                        'substitute': None,
                        'venue': absence['venue_code'],
                        'mentor_class': absence['mentor_class'],
                        'request_id': request_id,
                        'status': 'no_cover'
                    }
            
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
                
                # Find substitute (now passes target_date for absence checking)
                sub_teacher, new_pointer = get_next_substitute(
                    slot['period_id'], cycle_day, already_assigned_today, pointer, target_date=target_date
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
                    # Create a Pending request so it shows in Mission Control
                    request_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO substitute_request
                        (id, tenant_id, absence_id, period_id, substitute_id, status,
                         class_name, subject, venue_id, venue_name, request_date)
                        VALUES (?, ?, ?, ?, NULL, 'Pending', ?, ?, ?, ?, ?)
                    """, (request_id, TENANT_ID, absence_id, slot['period_id'],
                          slot['class_name'], slot['subject'],
                          slot['venue_id'], slot['venue_code'], target_date_str))
                    conn.commit()
                    
                    log_event(absence_id, 'no_cover', None,
                             f"[{target_date_str}] {slot['period_name']}: No substitute available",
                             request_id)
                    period_result['status'] = 'no_cover'
                    period_result['request_id'] = request_id
                
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
        
        # Get absent staff on this date
        absent_staff = get_absent_staff_on_date(target_date)
        
        # Get cycle day (default to 1 for now)
        cycle_day = get_cycle_day()  # Use current cycle day
        if False:  # cycle_day_config table not implemented yet
            cursor.execute("SELECT cycle_day FROM cycle_day_config_disabled WHERE calendar_date = ? AND tenant_id = ?",
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
            # Mentor duty - find nearest available teacher or any available
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
                ORDER BY 
                    CASE WHEN s.surname >= ? THEN 0 ELSE 1 END,
                    s.surname
            """, (TENANT_ID, req['absent_staff_id'], declined_by_id, target_date, target_date, pointer))
        
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


def get_eligible_terrain_staff(exclude_ids=None, target_date=None):
    """
    Get staff eligible for terrain duty, sorted by first name.
    Excludes: already assigned terrain this week, absent staff, explicitly excluded.
    """
    exclude_ids = exclude_ids or []
    
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
    
    # Get week boundaries (Mon-Fri of target date's week)
    weekday = target_date.weekday()
    monday = target_date - timedelta(days=weekday)
    friday = monday + timedelta(days=4)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all staff who can do duty
        cursor.execute("""
            SELECT id, display_name, first_name, surname
            FROM staff
            WHERE tenant_id = ? AND can_do_duty = 1 AND is_active = 1
            ORDER BY first_name ASC, surname ASC
        """, (TENANT_ID,))
        all_staff = [dict(row) for row in cursor.fetchall()]
        
        # Get staff already assigned terrain this week
        cursor.execute("""
            SELECT DISTINCT staff_id 
            FROM duty_roster 
            WHERE tenant_id = ? AND duty_type = 'terrain'
              AND duty_date >= ? AND duty_date <= ?
        """, (TENANT_ID, monday.isoformat(), friday.isoformat()))
        assigned_this_week = {row['staff_id'] for row in cursor.fetchall()}
        
        # Get absent staff
        absent_staff = set(get_absent_staff_on_date(target_date))
        
        # Filter eligible
        eligible = []
        for staff in all_staff:
            if staff['id'] in exclude_ids:
                continue
            if staff['id'] in assigned_this_week:
                continue
            if staff['id'] in absent_staff:
                continue
            eligible.append(staff)
        
        return eligible


def reassign_terrain_duty(duty_id, original_staff_id):
    """
    Reassign a terrain duty to the next eligible teacher.
    Returns the new assignee dict or None if no one available.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get the duty details
        cursor.execute("""
            SELECT dr.*, ta.area_name
            FROM duty_roster dr
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.id = ?
        """, (duty_id,))
        duty = cursor.fetchone()
        
        if not duty:
            return None
        
        duty = dict(duty)
        target_date = duty['duty_date']
        
        # Get eligible staff (excluding original)
        eligible = get_eligible_terrain_staff(
            exclude_ids=[original_staff_id],
            target_date=target_date
        )
        
        if not eligible:
            print(f"TERRAIN: No eligible staff to reassign duty {duty_id}")
            return None
        
        # Pick first eligible (alphabetical by first name)
        new_assignee = eligible[0]
        
        # Update the duty roster
        cursor.execute("""
            UPDATE duty_roster
            SET staff_id = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (new_assignee['id'], duty_id))
        
        # Log to duty_decline for audit trail
        cursor.execute("""
            INSERT INTO duty_decline (id, tenant_id, duty_type, staff_id, staff_name, duty_description, duty_date, reason, declined_at)
            VALUES (?, ?, 'terrain', ?, ?, ?, ?, 'absent', datetime('now'))
        """, (
            str(uuid.uuid4()),
            TENANT_ID,
            original_staff_id,
            duty.get('staff_name', 'Unknown'),
            f"Terrain: {duty.get('area_name', 'Unknown area')} - auto-reassigned due to absence",
            target_date
        ))
        
        conn.commit()
        
        print(f"TERRAIN: Reassigned {duty.get('area_name')} on {target_date} from {original_staff_id} to {new_assignee['display_name']}")
        return new_assignee


def handle_absent_teacher_duties(staff_id, start_date, end_date=None):
    """
    Check if absent teacher has any duties and handle them:
    1. Substitute assignments -> auto-reassign via existing function
    2. Terrain duty -> auto-reassign to next eligible
    3. Sport duty -> notify coordinator (Delene)
    
    Called after process_absence() in substitute.py
    Returns dict with results.
    """
    if isinstance(start_date, str):
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    if end_date is None:
        end_date = start_date
    elif isinstance(end_date, str):
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    results = {
        'substitute_reassigned': [],
        'terrain_reassigned': [],
        'sport_orphaned': [],
        'errors': []
    }
    
    # Get all dates in the absence range (weekdays only)
    absence_dates = get_weekdays_between(start_date, end_date)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get staff display name for logging
        cursor.execute("SELECT display_name FROM staff WHERE id = ?", (staff_id,))
        staff_row = cursor.fetchone()
        staff_name = staff_row['display_name'] if staff_row else 'Unknown'
        
        for target_date in absence_dates:
            target_date_str = target_date.isoformat()
            
            # === 1. CHECK SUBSTITUTE ASSIGNMENTS ===
            cursor.execute("""
                SELECT sr.id, sr.period_id, p.period_name, a.staff_id as absent_teacher_id,
                       s.display_name as absent_teacher_name
                FROM substitute_request sr
                JOIN absence a ON sr.absence_id = a.id
                JOIN staff s ON a.staff_id = s.id
                LEFT JOIN period p ON sr.period_id = p.id
                WHERE sr.substitute_id = ? 
                  AND sr.request_date = ?
                  AND sr.status = 'Assigned'
            """, (staff_id, target_date_str))
            
            sub_assignments = [dict(row) for row in cursor.fetchall()]
            
            for sub in sub_assignments:
                # Use existing reassign function
                new_sub = reassign_declined_request(sub['id'], staff_id)
                if new_sub:
                    results['substitute_reassigned'].append({
                        'date': target_date_str,
                        'period': sub.get('period_name', 'Roll Call'),
                        'for_teacher': sub['absent_teacher_name'],
                        'new_sub': new_sub['display_name']
                    })
                    print(f"SUB CLASH: {staff_name} was covering {sub['absent_teacher_name']} {sub.get('period_name', 'Roll Call')} on {target_date_str} -> reassigned to {new_sub['display_name']}")
                else:
                    results['errors'].append(f"No sub available for {sub.get('period_name', 'Roll Call')} on {target_date_str}")
            
            # === 2. CHECK TERRAIN DUTY ===
            cursor.execute("""
                SELECT dr.id, dr.duty_type, ta.area_name
                FROM duty_roster dr
                LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
                WHERE dr.staff_id = ? AND dr.duty_date = ? AND dr.duty_type IN ('terrain', 'homework')
            """, (staff_id, target_date_str))
            
            terrain_duties = [dict(row) for row in cursor.fetchall()]
            
            for duty in terrain_duties:
                new_assignee = reassign_terrain_duty(duty['id'], staff_id)
                if new_assignee:
                    results['terrain_reassigned'].append({
                        'date': target_date_str,
                        'duty_type': duty['duty_type'],
                        'area': duty.get('area_name', 'Homework Venue'),
                        'new_assignee': new_assignee['display_name']
                    })
                    print(f"TERRAIN CLASH: {staff_name} had {duty['duty_type']} on {target_date_str} -> reassigned to {new_assignee['display_name']}")
                else:
                    results['errors'].append(f"No one available for {duty['duty_type']} on {target_date_str}")
            
            # === 3. CHECK SPORT DUTY ===
            cursor.execute("""
                SELECT sd.id, sd.duty_type, sd.event_id, se.event_name, se.coordinator_id,
                       c.display_name as coordinator_name
                FROM sport_duty sd
                JOIN sport_event se ON sd.event_id = se.id
                LEFT JOIN staff c ON se.coordinator_id = c.id
                WHERE sd.staff_id = ? AND se.event_date = ?
            """, (staff_id, target_date_str))
            
            sport_duties = [dict(row) for row in cursor.fetchall()]
            
            for sport in sport_duties:
                results['sport_orphaned'].append({
                    'date': target_date_str,
                    'event_name': sport['event_name'],
                    'duty_type': sport['duty_type'],
                    'coordinator_id': sport.get('coordinator_id'),
                    'coordinator_name': sport.get('coordinator_name', 'Unassigned'),
                    'sport_duty_id': sport['id']
                })
                print(f"SPORT CLASH: {staff_name} had sport duty ({sport['duty_type']}) for {sport['event_name']} on {target_date_str}")
                
                # Send push notification to coordinator
                try:
                    from app.routes.push import send_sport_duty_orphaned_push
                    if sport.get('coordinator_id'):
                        send_sport_duty_orphaned_push(
                            coordinator_id=sport['coordinator_id'],
                            event_name=sport['event_name'],
                            duty_type=sport['duty_type'],
                            absent_staff_name=staff_name,
                            event_date=target_date_str
                        )
                except Exception as e:
                    print(f"Sport push error: {e}")
    
    return results


def get_mentor_register_cover(mentor_group_id, target_date=None):
    """
    Get the teacher to cover mentor register for an absent mentor.
    New logic (Jan 2026):
    1. Grade Backup Teacher
    2. Grade Head (if backup absent)
    3. None (flag for manual assignment at 07:15 meeting)
    
    Returns dict with 'staff_id', 'display_name', 'fallback_level' or None
    """
    if target_date is None:
        target_date = date.today()
    
    absent_staff = set(get_absent_staff_on_date(target_date))
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get grade_id from mentor_group
        cursor.execute("""
            SELECT grade_id FROM mentor_group WHERE id = ?
        """, (mentor_group_id,))
        mg_row = cursor.fetchone()
        
        if not mg_row or not mg_row['grade_id']:
            print(f"MENTOR COVER: No grade found for mentor_group {mentor_group_id}")
            return None
        
        grade_id = mg_row['grade_id']
        
        # Get backup config for this grade
        cursor.execute("""
            SELECT gbc.backup_staff_id, gbc.grade_head_staff_id,
                   b.display_name as backup_name,
                   h.display_name as head_name
            FROM grade_backup_config gbc
            JOIN staff b ON gbc.backup_staff_id = b.id
            JOIN staff h ON gbc.grade_head_staff_id = h.id
            WHERE gbc.grade_id = ?
        """, (grade_id,))
        config = cursor.fetchone()
        
        if not config:
            print(f"MENTOR COVER: No backup config for grade {grade_id}")
            return None
        
        # Try backup teacher first
        if config['backup_staff_id'] not in absent_staff:
            print(f"MENTOR COVER: Using backup {config['backup_name']}")
            return {
                'staff_id': config['backup_staff_id'],
                'display_name': config['backup_name'],
                'fallback_level': 'backup'
            }
        
        # Try grade head
        if config['grade_head_staff_id'] not in absent_staff:
            print(f"MENTOR COVER: Backup absent, using grade head {config['head_name']}")
            return {
                'staff_id': config['grade_head_staff_id'],
                'display_name': config['head_name'],
                'fallback_level': 'grade_head'
            }
        
        # Both absent - no cover available
        print(f"MENTOR COVER: Both backup ({config['backup_name']}) and head ({config['head_name']}) absent")
        return None
