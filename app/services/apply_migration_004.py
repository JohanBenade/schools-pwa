"""
Apply migration 004: Decline + Multi-day absence
Run once to update existing database
"""

from app.services.db import get_connection

def apply_migration():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if migration already applied
        cursor.execute("SELECT version FROM schema_version WHERE version = 4")
        if cursor.fetchone():
            print("Migration 004 already applied")
            return False
        
        # Absence table updates
        migrations = [
            "ALTER TABLE absence ADD COLUMN end_date TEXT",
            "ALTER TABLE absence ADD COLUMN is_open_ended INTEGER DEFAULT 0",
            "ALTER TABLE absence ADD COLUMN returned_early INTEGER DEFAULT 0",
            "ALTER TABLE absence ADD COLUMN returned_at TEXT",
            "ALTER TABLE absence ADD COLUMN return_reported_by_id TEXT",
            
            # Substitute request updates
            "ALTER TABLE substitute_request ADD COLUMN declined_at TEXT",
            "ALTER TABLE substitute_request ADD COLUMN declined_by_id TEXT",
            "ALTER TABLE substitute_request ADD COLUMN decline_reason TEXT",
            "ALTER TABLE substitute_request ADD COLUMN cancelled_at TEXT",
            "ALTER TABLE substitute_request ADD COLUMN cancel_reason TEXT",
            "ALTER TABLE substitute_request ADD COLUMN request_date TEXT",
            
            # Config update
            "UPDATE substitute_config SET decline_cutoff_minutes = 30 WHERE tenant_id = 'MARAGON'",
            
            # Indexes
            "CREATE INDEX IF NOT EXISTS idx_subreq_date ON substitute_request(request_date)",
            "CREATE INDEX IF NOT EXISTS idx_absence_dates ON absence(start_date, end_date)",
            
            # Version
            "INSERT INTO schema_version (version, description) VALUES (4, 'Decline flow + Multi-day absence support')"
        ]
        
        for sql in migrations:
            try:
                cursor.execute(sql)
                print(f"✓ {sql[:50]}...")
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    print(f"⏭ Column exists: {sql[:50]}...")
                else:
                    print(f"✗ Error: {e}")
        
        conn.commit()
        print("\n✅ Migration 004 complete!")
        return True

if __name__ == "__main__":
    apply_migration()
