"""
Migration 006: Homework Venue Duty Support
Extends duty_roster to handle both terrain and homework duties.
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
        print("Database doesn't exist yet, skipping migration 006")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT version FROM schema_version WHERE version = 6")
    if cursor.fetchone():
        print("Migration 006 already applied")
        conn.close()
        return
    
    print("Applying migration 006: Homework Venue Duty Support...")
    
    # Add duty_type column to duty_roster
    cursor.execute("PRAGMA table_info(duty_roster)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    if 'duty_type' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN duty_type TEXT DEFAULT 'terrain'")
        print("Added duty_type column to duty_roster")
    
    # Add homework_pointer_index to terrain_config
    cursor.execute("PRAGMA table_info(terrain_config)")
    columns = [row['name'] for row in cursor.fetchall()]
    
    if 'homework_pointer_index' not in columns:
        cursor.execute("ALTER TABLE terrain_config ADD COLUMN homework_pointer_index INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE terrain_config ADD COLUMN homework_pointer_updated_at TEXT")
        print("Added homework pointer to terrain_config")
    
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (6, 'Homework venue duty support')
    """)
    
    conn.commit()
    conn.close()
    print("Migration 006 complete!")


if __name__ == "__main__":
    apply_migration()
