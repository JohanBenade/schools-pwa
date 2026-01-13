"""
Migration 007: Allow NULL terrain_area_id for homework duties
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
        print("Database doesn't exist yet, skipping migration 007")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT version FROM schema_version WHERE version = 7")
    if cursor.fetchone():
        print("Migration 007 already applied")
        conn.close()
        return
    
    print("Applying migration 007: Allow NULL terrain_area_id...")
    
    # Recreate duty_roster with nullable terrain_area_id
    cursor.execute("PRAGMA table_info(duty_roster)")
    columns = cursor.fetchall()
    
    # Create new table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS duty_roster_new (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            duty_date TEXT NOT NULL,
            terrain_area_id TEXT,
            staff_id TEXT NOT NULL,
            duty_type TEXT DEFAULT 'terrain',
            status TEXT DEFAULT 'Scheduled',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Copy data
    cursor.execute("""
        INSERT INTO duty_roster_new (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status, created_at, updated_at)
        SELECT id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status, created_at, updated_at
        FROM duty_roster
    """)
    
    # Drop old and rename
    cursor.execute("DROP TABLE duty_roster")
    cursor.execute("ALTER TABLE duty_roster_new RENAME TO duty_roster")
    
    # Recreate indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_roster_tenant_date ON duty_roster(tenant_id, duty_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_roster_staff ON duty_roster(staff_id)")
    
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (7, 'Allow NULL terrain_area_id for homework duties')
    """)
    
    conn.commit()
    conn.close()
    print("Migration 007 complete!")


if __name__ == "__main__":
    apply_migration()
