"""
Migration 009: Sport Events Module
Creates sport_event and sport_duty tables for tracking sports events and staff assignments.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def apply_migration():
    db_path = get_db_path()
    
    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 009")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT version FROM schema_version WHERE version = 9")
    if cursor.fetchone():
        print("Migration 009 already applied")
        conn.close()
        return
    
    print("Applying migration 009: Sport Events Module...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sport_event (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            event_date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            event_name TEXT NOT NULL,
            sport_type TEXT NOT NULL,
            location_type TEXT NOT NULL DEFAULT 'Home',
            venue_name TEXT,
            affects_timetable INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    print("Created sport_event table")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sport_event_tenant_date ON sport_event(tenant_id, event_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sport_event_sport ON sport_event(tenant_id, sport_type)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sport_duty (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            staff_id TEXT NOT NULL,
            duty_type TEXT NOT NULL,
            duty_role TEXT,
            status TEXT DEFAULT 'Assigned',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (event_id) REFERENCES sport_event(id) ON DELETE CASCADE,
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """)
    print("Created sport_duty table")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sport_duty_event ON sport_duty(event_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sport_duty_staff ON sport_duty(staff_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sport_duty_tenant ON sport_duty(tenant_id)")
    
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (9, 'Sport events module - events and duty assignments')
    """)
    
    conn.commit()
    conn.close()
    print("Migration 009 complete!")


if __name__ == "__main__":
    apply_migration()
