"""
Migration 010: Terrain duty enhancements
- Add Homework Venue to terrain_area
- Add decline columns to duty_roster
- Create terrain_log table
"""
import uuid

def apply(cursor):
    results = []
    
    # 1. Add Homework Venue to terrain_area
    cursor.execute("SELECT id FROM terrain_area WHERE area_code = 'homework_venue'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO terrain_area (id, tenant_id, area_code, area_name, sort_order, is_active)
            VALUES (?, 'MARAGON', 'homework_venue', 'Homework Venue', 6, 1)
        """, (str(uuid.uuid4()),))
        results.append("Added Homework Venue")
    
    # 2. Add decline columns to duty_roster
    cursor.execute("PRAGMA table_info(duty_roster)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'declined_at' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN declined_at TEXT")
        results.append("Added duty_roster.declined_at")
    
    if 'decline_reason' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN decline_reason TEXT")
        results.append("Added duty_roster.decline_reason")
    
    if 'declined_by_id' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN declined_by_id TEXT")
        results.append("Added duty_roster.declined_by_id")
    
    if 'replacement_id' not in columns:
        cursor.execute("ALTER TABLE duty_roster ADD COLUMN replacement_id TEXT")
        results.append("Added duty_roster.replacement_id")
    
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
    results.append("Created terrain_log table")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_log_duty ON terrain_log(duty_roster_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_terrain_log_staff ON terrain_log(staff_id)")
    
    return results
