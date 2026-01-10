"""
Seed data for substitute allocation demo
- Creates tables if they don't exist
- 8 periods + 2 breaks
- Demo timetable for Ms Beatrix (sick teacher)
- Realistic timetables for ~30 teachers
- Substitute config initialization
"""

import uuid
from datetime import datetime
from app.services.db import get_connection

TENANT_ID = "MARAGON"


def init_substitute_tables():
    """Create substitute tables if they don't exist."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Period table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS period (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                period_number INTEGER NOT NULL,
                period_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_teaching INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_period_tenant ON period(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_period_sort ON period(tenant_id, sort_order)")
        
        # Timetable slot table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timetable_slot (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                staff_id TEXT NOT NULL,
                cycle_day INTEGER NOT NULL,
                period_id TEXT NOT NULL,
                class_name TEXT,
                subject TEXT,
                venue_id TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timetable_staff ON timetable_slot(staff_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timetable_day_period ON timetable_slot(tenant_id, cycle_day, period_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timetable_tenant ON timetable_slot(tenant_id)")
        
        # Substitute config table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS substitute_config (
                tenant_id TEXT PRIMARY KEY,
                pointer_surname TEXT DEFAULT 'A',
                pointer_updated_at TEXT,
                cycle_start_date TEXT,
                cycle_length INTEGER DEFAULT 7,
                quiet_hours_start TEXT DEFAULT '21:00',
                quiet_hours_end TEXT DEFAULT '06:00',
                decline_cutoff_minutes INTEGER DEFAULT 15,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        
        # Substitute log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS substitute_log (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                absence_id TEXT NOT NULL,
                substitute_request_id TEXT,
                event_type TEXT NOT NULL,
                staff_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sublog_absence ON substitute_log(absence_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sublog_tenant_time ON substitute_log(tenant_id, created_at DESC)")
        
        conn.commit()
        
    return True


def seed_periods():
    """Create period definitions for Maragon."""
    
    periods = [
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
        
        cursor.execute("DELETE FROM timetable_slot WHERE tenant_id = ?", (TENANT_ID,))
        
        beatrix_id = get_staff_by_surname(cursor, "du Toit")
        jacqueline_id = get_staff_by_surname(cursor, "Sekhula")
        
        period_ids = {}
        for p in [1, 2, 3, 4, 5, 6, 7]:
            period_ids[p] = get_period_id(cursor, p)
        
        b001_id = get_venue_id(cursor, "B001")
        b002_id = get_venue_id(cursor, "B002")
        
        slots_created = 0
        
        # BEATRIX'S TIMETABLE (Day 3) - 5 periods, free 3 and 6
        if beatrix_id:
            beatrix_slots = [
                (3, 1, "Grade 10A", "English", b001_id),
                (3, 2, "Grade 11B", "English", b001_id),
                (3, 4, "Grade 9C", "English", b001_id),
                (3, 5, "Grade 12A", "English", b001_id),
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
        
        # JACQUELINE'S TIMETABLE (Day 3) - Period 1 FREE for roll call
        if jacqueline_id:
            jacqueline_slots = [
                (3, 2, "Grade 10B", "English", b002_id),
                (3, 3, "Grade 9A", "English", b002_id),
                (3, 4, "Grade 11A", "English", b002_id),
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
        
        # OTHER TEACHERS - ~70% load
        cursor.execute("""
            SELECT id, surname FROM staff 
            WHERE tenant_id = ? AND is_active = 1 AND can_substitute = 1
            AND id NOT IN (?, ?)
            ORDER BY surname
        """, (TENANT_ID, beatrix_id or '', jacqueline_id or ''))
        
        other_teachers = cursor.fetchall()
        
        cursor.execute("""
            SELECT id FROM venue 
            WHERE tenant_id = ? AND venue_type = 'classroom'
        """, (TENANT_ID,))
        venues = cursor.fetchall()
        venue_list = [v[0] for v in venues] if venues else [b001_id]
        
        subjects = ["Mathematics", "Afrikaans", "Life Sciences", "Physical Sciences", 
                    "Geography", "History", "Accounting", "Business Studies", "Life Orientation"]
        
        import random
        random.seed(42)
        
        for teacher_id, surname in other_teachers:
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
    init_substitute_tables()  # Create tables first!
    
    results = {
        'periods': seed_periods(),
        'config': seed_substitute_config(),
        'timetable_slots': seed_demo_timetable(),
    }
    return results


if __name__ == "__main__":
    results = seed_all_substitute()
    print(f"Seeded: {results}")
