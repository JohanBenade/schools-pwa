"""
Duty Generator Service
Generates terrain duty and homework venue duty schedules.

Terrain Duty:
- 5 areas, 5 teachers per school day
- A-Z rotation by surname, advances by 5 each day
- Mon-Fri school days

Homework Venue:
- 1 teacher per day
- A-Z rotation by surname, advances by 1 each day
- Mon-Thu only (not Friday)
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional

def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def generate_id():
    return str(uuid.uuid4())

def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn

def get_duty_eligible_staff(tenant_id: str = "MARAGON") -> List[Dict]:
    """Get teaching staff eligible for duty, sorted A-Z by surname."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get staff who can do duty, sorted by surname then first_name
    cursor.execute("""
        SELECT id, first_name, surname, display_name
        FROM staff
        WHERE tenant_id = ? 
        AND is_active = 1
        AND can_do_duty = 1
        ORDER BY surname ASC, first_name ASC
    """, (tenant_id,))
    
    staff = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return staff

def get_terrain_areas(tenant_id: str = "MARAGON") -> List[Dict]:
    """Get terrain areas sorted by sort_order."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, area_code, area_name, sort_order
        FROM terrain_area
        WHERE tenant_id = ? AND is_active = 1
        ORDER BY sort_order ASC
    """, (tenant_id,))
    
    areas = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return areas

def get_school_days(tenant_id: str, start_date: date, count: int, exclude_friday: bool = False) -> List[Dict]:
    """Get next N school days from start_date."""
    conn = get_connection()
    cursor = conn.cursor()
    
    weekday_filter = "AND weekday != 'friday'" if exclude_friday else ""
    
    cursor.execute(f"""
        SELECT date, cycle_day, day_type, day_name, weekday, bell_schedule
        FROM school_calendar
        WHERE tenant_id = ?
        AND date >= ?
        AND is_school_day = 1
        {weekday_filter}
        ORDER BY date ASC
        LIMIT ?
    """, (tenant_id, start_date.isoformat(), count))
    
    days = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return days

def get_config(tenant_id: str = "MARAGON") -> Dict:
    """Get duty configuration."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM terrain_config WHERE tenant_id = ?", (tenant_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return {
        'pointer_index': 0,
        'homework_pointer_index': 0,
        'days_to_generate': 5
    }

def update_config(tenant_id: str, pointer_index: int = None, homework_pointer_index: int = None):
    """Update duty configuration."""
    conn = get_connection()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    if pointer_index is not None:
        cursor.execute("""
            UPDATE terrain_config 
            SET pointer_index = ?, pointer_updated_at = ?, updated_at = ?
            WHERE tenant_id = ?
        """, (pointer_index, now, now, tenant_id))
    
    if homework_pointer_index is not None:
        cursor.execute("""
            UPDATE terrain_config 
            SET homework_pointer_index = ?, homework_pointer_updated_at = ?, updated_at = ?
            WHERE tenant_id = ?
        """, (homework_pointer_index, now, now, tenant_id))
    
    conn.commit()
    conn.close()

def get_existing_duties(tenant_id: str, duty_type: str, from_date: date) -> List[str]:
    """Get dates that already have duties scheduled."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT DISTINCT duty_date
        FROM duty_roster
        WHERE tenant_id = ? AND duty_type = ? AND duty_date >= ?
    """, (tenant_id, duty_type, from_date.isoformat()))
    
    dates = [row['duty_date'] for row in cursor.fetchall()]
    conn.close()
    return dates

def create_duty(tenant_id: str, duty_date: str, staff_id: str, 
                terrain_area_id: str = None, duty_type: str = 'terrain'):
    """Create a single duty roster entry."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO duty_roster 
        (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Scheduled')
    """, (generate_id(), tenant_id, duty_date, terrain_area_id, staff_id, duty_type))
    
    conn.commit()
    conn.close()

def generate_terrain_duty(tenant_id: str = "MARAGON", days: int = 5) -> Dict:
    """
    Generate terrain duty schedule for next N school days.
    Returns summary of what was created.
    """
    config = get_config(tenant_id)
    staff = get_duty_eligible_staff(tenant_id)
    areas = get_terrain_areas(tenant_id)
    
    if not staff:
        return {'error': 'No eligible staff found', 'created': 0}
    
    if not areas:
        return {'error': 'No terrain areas found', 'created': 0}
    
    # Get school days (Mon-Fri)
    today = date.today()
    school_days = get_school_days(tenant_id, today, days, exclude_friday=False)
    
    # Get already scheduled dates
    existing = get_existing_duties(tenant_id, 'terrain', today)
    
    # Filter out already scheduled days
    days_to_schedule = [d for d in school_days if d['date'] not in existing]
    
    if not days_to_schedule:
        return {'message': 'All days already scheduled', 'created': 0}
    
    pointer = config.get('pointer_index', 0)
    staff_count = len(staff)
    area_count = len(areas)
    created = 0
    
    for day in days_to_schedule:
        # Assign 5 consecutive staff to 5 areas
        for i, area in enumerate(areas):
            staff_index = (pointer + i) % staff_count
            assigned_staff = staff[staff_index]
            
            create_duty(
                tenant_id=tenant_id,
                duty_date=day['date'],
                staff_id=assigned_staff['id'],
                terrain_area_id=area['id'],
                duty_type='terrain'
            )
            created += 1
        
        # Advance pointer by 5 (number of areas)
        pointer = (pointer + area_count) % staff_count
    
    # Save new pointer
    update_config(tenant_id, pointer_index=pointer)
    
    return {
        'message': f'Generated terrain duty for {len(days_to_schedule)} days',
        'created': created,
        'days': [d['date'] for d in days_to_schedule],
        'new_pointer': pointer
    }

def generate_homework_duty(tenant_id: str = "MARAGON", days: int = 5) -> Dict:
    """
    Generate homework venue duty schedule for next N school days (Mon-Thu only).
    Returns summary of what was created.
    """
    config = get_config(tenant_id)
    staff = get_duty_eligible_staff(tenant_id)
    
    if not staff:
        return {'error': 'No eligible staff found', 'created': 0}
    
    # Get school days (Mon-Thu only, exclude Friday)
    today = date.today()
    school_days = get_school_days(tenant_id, today, days, exclude_friday=True)
    
    # Get already scheduled dates
    existing = get_existing_duties(tenant_id, 'homework', today)
    
    # Filter out already scheduled days
    days_to_schedule = [d for d in school_days if d['date'] not in existing]
    
    if not days_to_schedule:
        return {'message': 'All days already scheduled', 'created': 0}
    
    pointer = config.get('homework_pointer_index', 0)
    staff_count = len(staff)
    created = 0
    
    for day in days_to_schedule:
        assigned_staff = staff[pointer % staff_count]
        
        create_duty(
            tenant_id=tenant_id,
            duty_date=day['date'],
            staff_id=assigned_staff['id'],
            terrain_area_id=None,  # No area for homework
            duty_type='homework'
        )
        created += 1
        
        # Advance pointer by 1
        pointer = (pointer + 1) % staff_count
    
    # Save new pointer
    update_config(tenant_id, homework_pointer_index=pointer)
    
    return {
        'message': f'Generated homework duty for {len(days_to_schedule)} days',
        'created': created,
        'days': [d['date'] for d in days_to_schedule],
        'new_pointer': pointer
    }

def generate_all_duties(tenant_id: str = "MARAGON", days: int = 5) -> Dict:
    """Generate both terrain and homework duties."""
    terrain_result = generate_terrain_duty(tenant_id, days)
    homework_result = generate_homework_duty(tenant_id, days)
    
    return {
        'terrain': terrain_result,
        'homework': homework_result
    }

def get_duties_for_date(tenant_id: str, duty_date: date, duty_type: str = None) -> List[Dict]:
    """Get all duties for a specific date."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if duty_type:
        cursor.execute("""
            SELECT dr.*, s.display_name, s.first_name, s.surname,
                   ta.area_code, ta.area_name
            FROM duty_roster dr
            JOIN staff s ON dr.staff_id = s.id
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.tenant_id = ? AND dr.duty_date = ? AND dr.duty_type = ?
            ORDER BY ta.sort_order ASC
        """, (tenant_id, duty_date.isoformat(), duty_type))
    else:
        cursor.execute("""
            SELECT dr.*, s.display_name, s.first_name, s.surname,
                   ta.area_code, ta.area_name
            FROM duty_roster dr
            JOIN staff s ON dr.staff_id = s.id
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.tenant_id = ? AND dr.duty_date = ?
            ORDER BY dr.duty_type ASC, ta.sort_order ASC
        """, (tenant_id, duty_date.isoformat()))
    
    duties = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return duties

def get_staff_duties(staff_id: str, from_date: date, to_date: date) -> List[Dict]:
    """Get all duties for a staff member in date range."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT dr.*, ta.area_code, ta.area_name
        FROM duty_roster dr
        LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
        WHERE dr.staff_id = ? AND dr.duty_date BETWEEN ? AND ?
        ORDER BY dr.duty_date ASC, dr.duty_type ASC
    """, (staff_id, from_date.isoformat(), to_date.isoformat()))
    
    duties = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return duties


if __name__ == "__main__":
    # Test generation
    print("Generating duties...")
    result = generate_all_duties()
    print(f"Terrain: {result['terrain']}")
    print(f"Homework: {result['homework']}")
