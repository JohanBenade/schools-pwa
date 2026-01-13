"""
Migration 005: Terrain Duty + My Daily Schedule
Run once to add new tables and seed reference data.
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime

def get_db_path():
    """Get database path."""
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def generate_id():
    return str(uuid.uuid4())

def apply_migration():
    """Apply migration 005 if not already applied."""
    db_path = get_db_path()
    
    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 005")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT version FROM schema_version WHERE version = 5")
    if cursor.fetchone():
        print("Migration 005 already applied")
        conn.close()
        return
    
    print("Applying migration 005: Terrain Duty + My Daily Schedule...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terrain_area (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            area_code TEXT NOT NULL,
            area_name TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_area_tenant ON terrain_area(tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_area_sort ON terrain_area(tenant_id, sort_order)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS school_calendar (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            date TEXT NOT NULL,
            cycle_day INTEGER,
            day_type TEXT NOT NULL,
            day_name TEXT,
            weekday TEXT NOT NULL,
            bell_schedule TEXT NOT NULL,
            is_school_day INTEGER DEFAULT 1,
            term INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(tenant_id, date)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_school_calendar_tenant_date ON school_calendar(tenant_id, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_school_calendar_school_day ON school_calendar(tenant_id, is_school_day, date)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bell_schedule (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            schedule_type TEXT NOT NULL,
            slot_type TEXT NOT NULL,
            slot_number INTEGER,
            slot_name TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            is_teaching INTEGER DEFAULT 0,
            is_break INTEGER DEFAULT 0,
            sort_order INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bell_schedule_tenant_type ON bell_schedule(tenant_id, schedule_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bell_schedule_breaks ON bell_schedule(tenant_id, is_break)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teacher_meeting (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            staff_id TEXT NOT NULL,
            meeting_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            title TEXT NOT NULL,
            meeting_type TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_teacher_meeting_staff ON teacher_meeting(staff_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_teacher_meeting_date ON teacher_meeting(tenant_id, meeting_date)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terrain_config (
            tenant_id TEXT PRIMARY KEY,
            pointer_index INTEGER DEFAULT 0,
            pointer_updated_at TEXT,
            morning_duty_time TEXT DEFAULT '07:15',
            reminder_evening_time TEXT DEFAULT '18:00',
            reminder_morning_time TEXT DEFAULT '06:30',
            reminder_before_minutes INTEGER DEFAULT 15,
            days_to_generate INTEGER DEFAULT 5,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    cursor.execute("PRAGMA table_info(duty_roster)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    if 'zone_id' in columns and 'terrain_area_id' not in columns:
        print("Renaming duty_roster.zone_id to terrain_area_id...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duty_roster_new (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                duty_date TEXT NOT NULL,
                terrain_area_id TEXT NOT NULL,
                staff_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Scheduled',
                confirmed_at TEXT,
                reminder_evening_sent INTEGER NOT NULL DEFAULT 0,
                reminder_morning_sent INTEGER NOT NULL DEFAULT 0,
                reminder_before_sent INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        cursor.execute("""
            INSERT INTO duty_roster_new 
            SELECT id, tenant_id, duty_date, zone_id, staff_id, status, confirmed_at,
                   reminder_evening_sent, reminder_morning_sent, reminder_before_sent,
                   notes, created_at, updated_at
            FROM duty_roster
        """)
        cursor.execute("DROP TABLE duty_roster")
        cursor.execute("ALTER TABLE duty_roster_new RENAME TO duty_roster")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_date ON duty_roster(duty_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_staff ON duty_roster(staff_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_tenant_date ON duty_roster(tenant_id, duty_date)")
    
    tenant_id = "MARAGON"
    
    terrain_areas = [
        ("quad", "Quad", 1),
        ("praise_park", "Praise Park / Tuck shop", 2),
        ("down_under", "Down under", 3),
        ("pavilion", "Pavilion", 4),
        ("boundaries", "Boundaries", 5),
    ]
    
    for area_code, area_name, sort_order in terrain_areas:
        cursor.execute("""
            INSERT OR IGNORE INTO terrain_area (id, tenant_id, area_code, area_name, sort_order)
            VALUES (?, ?, ?, ?, ?)
        """, (generate_id(), tenant_id, area_code, area_name, sort_order))
    
    print(f"Seeded {len(terrain_areas)} terrain areas")
    
    type_a_slots = [
        ("register", None, "Register", "07:30", "07:40", 0, 0, 1),
        ("assembly", None, "Assembly", "07:40", "08:20", 0, 0, 2),
        ("period", 1, "Period 1", "08:20", "09:05", 1, 0, 3),
        ("period", 2, "Period 2", "09:05", "09:50", 1, 0, 4),
        ("break", 1, "Break 1", "09:50", "10:10", 0, 1, 5),
        ("period", 3, "Period 3", "10:10", "10:55", 1, 0, 6),
        ("period", 4, "Period 4", "10:55", "11:40", 1, 0, 7),
        ("period", 5, "Period 5", "11:40", "12:25", 1, 0, 8),
        ("break", 2, "Break 2", "12:25", "12:45", 0, 1, 9),
        ("period", 6, "Period 6", "12:45", "13:30", 1, 0, 10),
        ("period", 7, "Period 7", "13:30", "14:15", 1, 0, 11),
    ]
    
    type_b_slots = [
        ("test", None, "Test", "07:30", "08:40", 0, 0, 1),
        ("period", 1, "Period 1", "08:40", "09:22", 1, 0, 2),
        ("period", 2, "Period 2", "09:22", "10:04", 1, 0, 3),
        ("break", 1, "Break 1", "10:04", "10:24", 0, 1, 4),
        ("period", 3, "Period 3", "10:24", "11:06", 1, 0, 5),
        ("period", 4, "Period 4", "11:06", "11:48", 1, 0, 6),
        ("period", 5, "Period 5", "11:48", "12:30", 1, 0, 7),
        ("break", 2, "Break 2", "12:30", "12:50", 0, 1, 8),
        ("period", 6, "Period 6", "12:50", "13:32", 1, 0, 9),
        ("period", 7, "Period 7", "13:32", "14:15", 1, 0, 10),
    ]
    
    type_c_slots = [
        ("register", None, "Register", "07:30", "07:40", 0, 0, 1),
        ("clubs", None, "Clubs/Mentor", "07:40", "08:30", 0, 0, 2),
        ("period", 1, "Period 1", "08:30", "09:10", 1, 0, 3),
        ("period", 2, "Period 2", "09:10", "09:50", 1, 0, 4),
        ("period", 3, "Period 3", "09:50", "10:30", 1, 0, 5),
        ("break", 1, "Rec Time", "10:30", "11:05", 0, 1, 6),
        ("period", 4, "Period 4", "11:05", "11:45", 1, 0, 7),
        ("period", 5, "Period 5", "11:45", "12:25", 1, 0, 8),
        ("period", 6, "Period 6", "12:25", "13:05", 1, 0, 9),
        ("period", 7, "Period 7", "13:05", "13:45", 1, 0, 10),
    ]
    
    bell_count = 0
    for schedule_type, slots in [("type_a", type_a_slots), ("type_b", type_b_slots), ("type_c", type_c_slots)]:
        for slot_type, slot_number, slot_name, start_time, end_time, is_teaching, is_break, sort_order in slots:
            cursor.execute("""
                INSERT OR IGNORE INTO bell_schedule 
                (id, tenant_id, schedule_type, slot_type, slot_number, slot_name, 
                 start_time, end_time, is_teaching, is_break, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (generate_id(), tenant_id, schedule_type, slot_type, slot_number, 
                  slot_name, start_time, end_time, is_teaching, is_break, sort_order))
            bell_count += 1
    
    print(f"Seeded {bell_count} bell schedule slots")
    
    cursor.execute("""
        INSERT OR IGNORE INTO terrain_config (tenant_id, pointer_index, created_at)
        VALUES (?, 0, ?)
    """, (tenant_id, datetime.now().isoformat()))
    
    print("Seeded terrain config")
    
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (5, 'Terrain duty + My Daily Schedule - areas, calendar, bell schedules, meetings, config')
    """)
    
    conn.commit()
    conn.close()
    
    print("Migration 005 complete!")


if __name__ == "__main__":
    apply_migration()
