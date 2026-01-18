"""
Migration 010: Terrain duty enhancements
- Add Homework Venue to terrain_area
- Add decline columns to duty_roster
- Create terrain_log table
"""

def run(conn):
    cursor = conn.cursor()
    
    # 1. Add Homework Venue to terrain_area
    cursor.execute("SELECT id FROM terrain_area WHERE area_code = 'homework_venue'")
    if not cursor.fetchone():
        import uuid
        cursor.execute("""
            INSERT INTO terrain_area (id, tenant_id, area_code, area_name, sort_order, is_active)
            VALUES (?, 'MARAGON', 'homework_venue', 'Homework Venue', 6, 1)
        """, (str(uuid.uuid4()),))
        print("  Added Homework Venue")
    
    # 2. Add decline columns to duty_roster
    cursor.execute("PRAGMA table_info(duty_roster)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'declined_at' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN declined_at TEXT")
        print("  Added duty_roster.declined_at")
    
    if 'decline_reason' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN decline_reason TEXT")
        print("  Added duty_roster.decline_reason")
    
    if 'declined_by_id' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN declined_by_id TEXT")
        print("  Added duty_roster.declined_by_id")
    
    if 'replacement_id' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN replacement_id TEXT")
        print("  Added duty_roster.replacement_id")
    
    # 3. Create terrain_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS terrain_log (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            duty_roster_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            staff_id TEXT,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (duty_roster_id) REFERENCES duty_roster(id),
            FOREIGN KEY (staff_id) REFERENCES staff(id)
        )
    """)
    print("  Created terrain_log table")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_log_duty ON terrain_log(duty_roster_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_log_staff ON terrain_log(staff_id)")
    
    # 4. Update schema version
    cursor.execute("""
        INSERT OR REPLACE INTO schema_version (version, description, applied_at)
        VALUES (10, 'Terrain duty enhancements - Homework venue, decline tracking, terrain_log', datetime('now'))
    """)
    
    conn.commit()
    print("Migration 010 complete!")

if __name__ == "__main__":
    import sqlite3
    conn = sqlite3.connect('/var/data/schoolops.db')
    run(conn)
    conn.close()
