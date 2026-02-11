"""
Duty Generator Service
Generates terrain duty and homework venue duty schedules.

Terrain Duty:
- 5 areas, 5 teachers per school day (Mon-Fri)
- Rotation by first_name ASC, advances by 5+ per day
- Skips teachers with homework duty or active absence

Homework Venue:
- 1 teacher per day (Mon-Thu only)
- Rotation by first_name DESC, advances by 1 per day
- Skips teachers with active absence

Generation order: homework FIRST, then terrain (homework wins overlap).
"""

import uuid
from datetime import date
from typing import List, Dict, Optional, Tuple
from app.services.db import get_connection

TENANT_ID = "MARAGON"


def generate_id():
    return str(uuid.uuid4())


def get_eligible_staff_asc(conn) -> List[Dict]:
    """Get duty-eligible staff sorted by first_name ASC (for terrain)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, first_name, surname, display_name
        FROM staff
        WHERE tenant_id = ? AND is_active = 1 AND can_do_duty = 1
        ORDER BY first_name ASC, surname ASC
    """, (TENANT_ID,))
    return [dict(row) for row in cursor.fetchall()]


def get_eligible_staff_desc(conn) -> List[Dict]:
    """Get duty-eligible staff sorted by first_name DESC (for homework)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, first_name, surname, display_name
        FROM staff
        WHERE tenant_id = ? AND is_active = 1 AND can_do_duty = 1
        ORDER BY first_name DESC, surname DESC
    """, (TENANT_ID,))
    return [dict(row) for row in cursor.fetchall()]


def get_terrain_areas(conn) -> List[Dict]:
    """Get active terrain areas (excludes Homework Venue)."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, area_code, area_name, sort_order
        FROM terrain_area
        WHERE tenant_id = ? AND is_active = 1
        ORDER BY sort_order ASC
    """, (TENANT_ID,))
    return [dict(row) for row in cursor.fetchall()]


def get_school_days_in_range(conn, start_date: date, end_date: date) -> List[Dict]:
    """Get school days in date range from school_calendar."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, cycle_day, day_name, weekday
        FROM school_calendar
        WHERE tenant_id = ? AND date >= ? AND date <= ? AND is_school_day = 1
        ORDER BY date ASC
    """, (TENANT_ID, start_date.isoformat(), end_date.isoformat()))
    return [dict(row) for row in cursor.fetchall()]


def get_absent_staff_ids(conn, date_str: str) -> set:
    """Get staff IDs with active absence on a specific date."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT staff_id FROM absence
        WHERE tenant_id = ?
        AND absence_date <= ?
        AND (end_date >= ? OR end_date IS NULL OR is_open_ended = 1)
        AND status IN ('Reported', 'Covered', 'Partial')
    """, (TENANT_ID, date_str, date_str))
    return {row['staff_id'] for row in cursor.fetchall()}


def get_existing_duty_dates(conn, start_date: date, end_date: date) -> List[str]:
    """Get dates that already have duties in the range."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT duty_date
        FROM duty_roster
        WHERE tenant_id = ? AND duty_date >= ? AND duty_date <= ?
        ORDER BY duty_date
    """, (TENANT_ID, start_date.isoformat(), end_date.isoformat()))
    return [row['duty_date'] for row in cursor.fetchall()]


def get_config(conn) -> Dict:
    """Get terrain_config pointers."""
    cursor = conn.cursor()
    cursor.execute("SELECT pointer_index, homework_pointer_index FROM terrain_config WHERE tenant_id = ?", (TENANT_ID,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return {'pointer_index': 0, 'homework_pointer_index': 0}


def _assign_homework_for_day(staff_desc: List[Dict], pointer: int, absent_ids: set) -> Tuple[Optional[Dict], int]:
    """
    Assign 1 homework teacher for a day.
    Returns (assigned_staff_dict_or_None, new_pointer).
    """
    staff_count = len(staff_desc)
    checked = 0
    while checked < staff_count:
        idx = pointer % staff_count
        candidate = staff_desc[idx]
        pointer += 1
        checked += 1
        if candidate['id'] not in absent_ids:
            return candidate, pointer % staff_count
    return None, pointer % staff_count


def _assign_terrain_for_day(staff_asc: List[Dict], pointer: int, areas: List[Dict],
                            absent_ids: set, homework_staff_id: Optional[str]) -> Tuple[List[Dict], int]:
    """
    Assign 5 terrain teachers for a day.
    Returns (list_of_assignments, new_pointer).
    Each assignment: {staff_id, display_name, area_id, area_name, area_code}
    """
    staff_count = len(staff_asc)
    area_count = len(areas)
    assignments = []
    area_idx = 0
    checked = 0

    while area_idx < area_count and checked < staff_count:
        idx = pointer % staff_count
        candidate = staff_asc[idx]
        pointer += 1
        checked += 1

        # Skip if absent or has homework today
        if candidate['id'] in absent_ids:
            continue
        if homework_staff_id and candidate['id'] == homework_staff_id:
            continue

        area = areas[area_idx]
        assignments.append({
            'staff_id': candidate['id'],
            'display_name': candidate['display_name'],
            'area_id': area['id'],
            'area_name': area['area_name'],
            'area_code': area['area_code']
        })
        area_idx += 1

    return assignments, pointer % staff_count


def preview_duties(start_date: date, end_date: date) -> Dict:
    """
    Generate a preview without committing to database.
    Returns preview data structure for UI display.
    """
    with get_connection() as conn:
        # Validate
        staff_asc = get_eligible_staff_asc(conn)
        staff_desc = get_eligible_staff_desc(conn)
        areas = get_terrain_areas(conn)

        if not staff_asc:
            return {'error': 'No eligible staff found'}
        if not areas:
            return {'error': 'No terrain areas found'}

        school_days = get_school_days_in_range(conn, start_date, end_date)
        if not school_days:
            return {'error': 'No school days in selected range'}

        existing = get_existing_duty_dates(conn, start_date, end_date)
        if existing:
            return {'error': 'duties_exist', 'existing_dates': existing}

        config = get_config(conn)
        terrain_pointer = config['pointer_index']
        homework_pointer = config['homework_pointer_index']

        days_preview = []
        terrain_count = 0
        homework_count = 0

        for day in school_days:
            date_str = day['date']
            weekday = day['weekday'].lower()
            is_friday = weekday == 'friday'
            absent_ids = get_absent_staff_ids(conn, date_str)

            day_data = {
                'date': date_str,
                'day_name': day.get('day_name') or weekday.capitalize(),
                'weekday': weekday,
                'terrain': [],
                'homework': None,
                'skipped': []
            }

            # Step 1: Homework (Mon-Thu only)
            homework_staff_id = None
            if not is_friday:
                hw_staff, homework_pointer = _assign_homework_for_day(
                    staff_desc, homework_pointer, absent_ids
                )
                if hw_staff:
                    day_data['homework'] = hw_staff['display_name']
                    homework_staff_id = hw_staff['id']
                    homework_count += 1

            # Step 2: Terrain (Mon-Fri)
            terrain_assignments, terrain_pointer = _assign_terrain_for_day(
                staff_asc, terrain_pointer, areas, absent_ids, homework_staff_id
            )
            day_data['terrain'] = terrain_assignments
            terrain_count += len(terrain_assignments)

            days_preview.append(day_data)

        return {
            'success': True,
            'days': days_preview,
            'terrain_count': terrain_count,
            'homework_count': homework_count,
            'total_count': terrain_count + homework_count,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }


def generate_duties(start_date: date, end_date: date) -> Dict:
    """
    Generate and commit duties to database.
    Returns summary of what was created.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Validate
        staff_asc = get_eligible_staff_asc(conn)
        staff_desc = get_eligible_staff_desc(conn)
        areas = get_terrain_areas(conn)

        if not staff_asc:
            return {'error': 'No eligible staff found'}
        if not areas:
            return {'error': 'No terrain areas found'}

        school_days = get_school_days_in_range(conn, start_date, end_date)
        if not school_days:
            return {'error': 'No school days in selected range'}

        existing = get_existing_duty_dates(conn, start_date, end_date)
        if existing:
            return {'error': 'duties_exist', 'existing_dates': existing}

        config = get_config(conn)
        terrain_pointer = config['pointer_index']
        homework_pointer = config['homework_pointer_index']

        terrain_count = 0
        homework_count = 0

        for day in school_days:
            date_str = day['date']
            weekday = day['weekday'].lower()
            is_friday = weekday == 'friday'
            absent_ids = get_absent_staff_ids(conn, date_str)

            # Step 1: Homework (Mon-Thu only)
            homework_staff_id = None
            if not is_friday:
                hw_staff, homework_pointer = _assign_homework_for_day(
                    staff_desc, homework_pointer, absent_ids
                )
                if hw_staff:
                    cursor.execute("""
                        INSERT INTO duty_roster
                        (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status)
                        VALUES (?, ?, ?, NULL, ?, 'homework', 'Scheduled')
                    """, (generate_id(), TENANT_ID, date_str, hw_staff['id']))
                    homework_staff_id = hw_staff['id']
                    homework_count += 1

            # Step 2: Terrain (Mon-Fri)
            terrain_assignments, terrain_pointer = _assign_terrain_for_day(
                staff_asc, terrain_pointer, areas, absent_ids, homework_staff_id
            )
            for assignment in terrain_assignments:
                cursor.execute("""
                    INSERT INTO duty_roster
                    (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status)
                    VALUES (?, ?, ?, ?, ?, 'terrain', 'Scheduled')
                """, (generate_id(), TENANT_ID, date_str, assignment['area_id'], assignment['staff_id']))
                terrain_count += 1

            # Save updated pointers
            cursor.execute("""
                UPDATE terrain_config
                SET pointer_index = ?, homework_pointer_index = ?,
                    pointer_updated_at = datetime('now'), homework_pointer_updated_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE tenant_id = ?
            """, (terrain_pointer, homework_pointer, TENANT_ID))

        conn.commit()

        return {
            'success': True,
            'terrain_count': terrain_count,
            'homework_count': homework_count,
            'total_count': terrain_count + homework_count,
            'days': len(school_days)
        }


def clear_duties_in_range(start_date: date, end_date: date) -> Dict:
    """Clear all duties in a date range."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM duty_roster
            WHERE tenant_id = ? AND duty_date >= ? AND duty_date <= ?
        """, (TENANT_ID, start_date.isoformat(), end_date.isoformat()))
        deleted = cursor.rowcount
        conn.commit()
        return {'success': True, 'deleted': deleted}
