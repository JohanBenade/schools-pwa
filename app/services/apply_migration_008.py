"""
Migration 008: Fix Bell Schedule Slot Names
Updates placeholder slot names to proper values.
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
        print("Database doesn't exist yet, skipping migration 008")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT version FROM schema_version WHERE version = 8")
    if cursor.fetchone():
        print("Migration 008 already applied")
        conn.close()
        return
    
    print("Applying migration 008: Fix Bell Schedule Slot Names...")
    
    # Update 07:30 slot to "Register" for all schedule types
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Register'
        WHERE start_time = '07:30' AND slot_type = 'register'
    """)
    register_updated = cursor.rowcount
    print(f"Updated {register_updated} register slots")
    
    # Update 07:40 assembly slot
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Assembly'
        WHERE slot_type = 'assembly'
    """)
    assembly_updated = cursor.rowcount
    print(f"Updated {assembly_updated} assembly slots")
    
    # Update break slots
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Break'
        WHERE slot_type = 'break' AND slot_name LIKE '%Test%'
    """)
    break_updated = cursor.rowcount
    print(f"Updated {break_updated} break slots")
    
    # Update study slot
    cursor.execute("""
        UPDATE bell_schedule 
        SET slot_name = 'Study'
        WHERE slot_type = 'study' AND slot_name LIKE '%Test%'
    """)
    study_updated = cursor.rowcount
    print(f"Updated {study_updated} study slots")
    
    # Update period slots to just show "Period X"
    for i in range(1, 8):
        cursor.execute(f"""
            UPDATE bell_schedule 
            SET slot_name = 'Period {i}'
            WHERE slot_type = 'period' AND slot_number = {i} AND slot_name LIKE '%Test%'
        """)
    
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (8, 'Fix bell schedule slot names')
    """)
    
    conn.commit()
    conn.close()
    print("Migration 008 complete!")


if __name__ == "__main__":
    apply_migration()
