"""
Seed data for substitute allocation demo
- 8 periods + 2 breaks
- Demo timetable for Ms Beatrix (sick teacher)
- Realistic timetables for ~30 teachers
- Substitute config initialization
"""

import uuid
from datetime import datetime
from app.services.db import get_connection

TENANT_ID = "MARAGON"


def seed_periods():
    """Create period definitions for Maragon."""
    
    periods = [
        # (period_number, name, start, end, is_teaching, sort_order)
        (1, "Period 1", "07:30", "08:15", 1, 1),
        (2, "Period 2", "08:20", "09:05", 1, 2),
        (3, "Period 3", "09:10", "09:55", 1, 3),
        (0, "Break 1", "09:55", "10:25", 0, 4),
        (4, "Period 4", "10:25", "11:10", 1, 5),
        (5, "Period 5", "11:15", "12:00", 1, 6),
        (6, "Period 6", "12:05", "12:50", 1, 7),
        (0, "Break 2", "12:50", "13:20", 0, 8),
        (7, "Period 7", "13:20", "14:05", 1, 9),
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing periods
        cursor.execute("DELETE FROM period WHERE tenant_id = ?", (TENANT_ID,))
        
        for p_num, p_name, start, end, is_teaching, sort in periods:
            cursor.execute("""
                INSERT INTO period (id, tenant_id, period_number, period_name, 
                                   start_time, end_time, is_teaching, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), TENANT_ID, p_num, p_name, start, end, is_teaching, sort))
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM period WHERE tenant_id = ?", (TENANT_ID,))
        count = cursor.fetchone()[0]
        
    return count


def seed_substitute_config():
    """Initialize substitute configuration."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO substitute_config 
            (tenant_id, pointer_surname, pointer_updated_at, cycle_start_date, 
             cycle_length, quiet_hours_start, quiet_hours_end, decline_cutoff_minutes)
            VALUES (?, 'A', ?, '2026-01-15', 7, '21:00', '06:00', 15)
        """, (TENANT_ID, datetime.now().isoformat()))
        
        conn.commit()
    
    return 1


def get_staff_by_surname(cursor, surname):
    """Get staff ID by surname."""
    cursor.execute("""
        SELECT id FROM staff 
        WHERE tenant_id = ? AND surname = ? AND is_active = 1
        LIMIT 1
    """, (TENANT_ID, surname))
    row = cursor.fetchone()
    return row[0] if row else None


def get_period_id(cursor, period_number):
    """Get period ID by period number."""
    cursor.execute("""
        SELECT id FROM period 
        WHERE tenant_id = ? AND period_number = ? AND is_teaching = 1
        LIMIT 1
    """, (TENANT_ID, period_number))
    row = cursor.fetchone()
    return row[0] if row else None


def get_venue_id(cursor, venue_code):
    """Get venue ID by code."""
    cursor.execute("""
        SELECT id FROM venue 
        WHERE tenant_id = ? AND venue_code = ?
        LIMIT 1
    """, (TENANT_ID, venue_code))
    row = cursor.fetchone()
    return row[0] if row else None


def seed_demo_timetable():
    """
    Create demo timetable:
    - Ms Beatrix (B001) teaches periods 1,2,4,5,7 on Day 3
    - Ensure some teachers are FREE during those periods
    - Ensure Ms Jacqueline (B002) has a timetable (for adjacent roll call)
    """
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing timetable
        cursor.execute("DELETE FROM timetable_slot WHERE tenant_id = ?", (TENANT_ID,))
        
        # Get staff IDs for key demo actors
        beatrix_id = get_staff_by_surname(cursor, "du Toit")      # Sick teacher, B001
        jacqueline_id = get_staff_by_surname(cursor, "Sekhula")   # Adjacent B002, roll call
        
        # Get period IDs
        period_ids = {}
        for p in [1, 2, 3, 4, 5, 6, 7]:
            period_ids[p] = get_period_id(cursor, p)
        
        # Get venue IDs
        b001_id = get_venue_id(cursor, "B001")
        b002_id = get_venue_id(cursor, "B002")
        
        slots_created = 0
        
        # === BEATRIX'S TIMETABLE (Day 3) ===
        # She teaches 5 periods, free periods 3 and 6
        if beatrix_id:
            beatrix_slots = [
                # (cycle_day, period, class_name, subject, venue_id)
                (3, 1, "Grade 10A", "English", b001_id),
                (3, 2, "Grade 11B", "English", b001_id),
                # Period 3 - FREE
                (3, 4, "Grade 9C", "English", b001_id),
                (3, 5, "Grade 12A", "English", b001_id),
                # Period 6 - FREE
                (3, 7, "Grade 8D", "English", b001_id),
            ]
            
            for cycle_day, period, class_name, subject, venue_id in beatrix_slots:
                period_id = period_ids.get(period)
                if period_id:
                    cursor.execute("""
                        INSERT INTO timetable_slot 
                        (id, tenant_id, staff_id, cycle_day, period_id, class_name, subject, venue_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), TENANT_ID, beatrix_id, cycle_day, period_id, 
                          class_name, subject, venue_id))
                    slots_created += 1
        
        # === JACQUELINE'S TIMETABLE (Day 3) ===
        # She's in B002, teaches some periods but available for roll call assist
        if jacqueline_id:
            jacqueline_slots = [
                # Period 1 - FREE (available for Beatrix's mentor roll call!)
                (3, 2, "Grade 10B", "English", b002_id),
                (3, 3, "Grade 9A", "English", b002_id),
                (3, 4, "Grade 11A", "English", b002_id),
                # Period 5 - FREE
                (3, 6, "Grade 12B", "English", b002_id),
                (3, 7, "Grade 8A", "English", b002_id),
            ]
            
            for cycle_day, period, class_name, subject, venue_id in jacqueline_slots:
                period_id = period_ids.get(period)
                if period_id:
                    cursor.execute("""
                        INSERT INTO timetable_slot 
                        (id, tenant_id, staff_id, cycle_day, period_id, class_name, subject, venue_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), TENANT_ID, jacqueline_id, cycle_day, period_id, 
                          class_name, subject, venue_id))
                    slots_created += 1
        
        # === OTHER TEACHERS TIMETABLES ===
        # Create realistic ~70% teaching load for all other teachers
        # This ensures some are FREE when Beatrix needs cover
        
        cursor.execute("""
            SELECT id, surname FROM staff 
            WHERE tenant_id = ? AND is_active = 1 AND can_substitute = 1
            AND id NOT IN (?, ?)
            ORDER BY surname
        """, (TENANT_ID, beatrix_id or '', jacqueline_id or ''))
        
        other_teachers = cursor.fetchall()
        
        # Get all venues for variety
        cursor.execute("""
            SELECT id, venue_code FROM venue 
            WHERE tenant_id = ? AND venue_type = 'classroom'
        """, (TENANT_ID,))
        venues = cursor.fetchall()
        venue_list = [v[0] for v in venues] if venues else [b001_id]
        
        subjects = ["Mathematics", "Afrikaans", "Life Sciences", "Physical Sciences", 
                    "Geography", "History", "Accounting", "Business Studies", "Life Orientation"]
        
        import random
        random.seed(42)  # Reproducible for demo
        
        for teacher_id, surname in other_teachers:
            # Each teacher teaches ~5 periods on Day 3 (out of 7)
            # Random selection ensures some are free when Beatrix needs cover
            teaching_periods = random.sample([1, 2, 3, 4, 5, 6, 7], k=random.randint(4, 6))
            
            for period in teaching_periods:
                period_id = period_ids.get(period)
                venue_id = random.choice(venue_list) if venue_list else None
                subject = random.choice(subjects)
                grade = random.choice([8, 9, 10, 11, 12])
                class_letter = random.choice(['A', 'B', 'C', 'D'])
                
                if period_id:
                    cursor.execute("""
                        INSERT INTO timetable_slot 
                        (id, tenant_id, staff_id, cycle_day, period_id, class_name, subject, venue_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (str(uuid.uuid4()), TENANT_ID, teacher_id, 3, period_id, 
                          f"Grade {grade}{class_letter}", subject, venue_id))
                    slots_created += 1
        
        conn.commit()
        
    return slots_created


def seed_all_substitute():
    """Run all substitute seeding."""
    results = {
        'periods': seed_periods(),
        'config': seed_substitute_config(),
        'timetable_slots': seed_demo_timetable(),
    }
    return results


if __name__ == "__main__":
    results = seed_all_substitute()
    print(f"Seeded: {results}")
