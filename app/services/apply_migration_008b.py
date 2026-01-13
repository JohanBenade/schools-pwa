"""
Migration 008b: Fix ALL Bell Schedule Slot Names
More aggressive fix - updates by start_time regardless of slot_type.
"""

import sqlite3
from pathlib import Path

def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def apply_migration():
    db_path = get_db_path()
    
    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 008b")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("Applying migration 008b: Fix ALL Bell Schedule Slot Names...")
    
    # Fix ALL 07:30 slots to "Register"
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Register', slot_type = 'register'
        WHERE start_time = '07:30'
    """)
    print(f"Updated {cursor.rowcount} register slots (07:30)")
    
    # Fix ALL 07:40 slots to "Assembly"  
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Assembly', slot_type = 'assembly'
        WHERE start_time = '07:40'
    """)
    print(f"Updated {cursor.rowcount} assembly slots (07:40)")
    
    # Fix any remaining "Test" slot names
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Break'
        WHERE slot_name LIKE '%Test%' AND is_break = 1
    """)
    print(f"Updated {cursor.rowcount} break slots")
    
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Study'
        WHERE slot_name LIKE '%Test%' AND slot_type = 'study'
    """)
    print(f"Updated {cursor.rowcount} study slots")
    
    # Show current state
    cursor.execute("SELECT schedule_type, start_time, slot_name FROM bell_schedule WHERE start_time IN ('07:30', '07:40') ORDER BY schedule_type, start_time")
    for row in cursor.fetchall():
        print(f"  {row['schedule_type']} {row['start_time']}: {row['slot_name']}")
    
    conn.commit()
    conn.close()
    print("Migration 008b complete!")


if __name__ == "__main__":
    apply_migration()
