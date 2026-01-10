"""
Migration v3: Add substitute allocation fields to existing tables
"""

from app.services.db import get_connection


def migrate():
    """Add new columns to absence and substitute_request tables."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check and add columns to absence table
        cursor.execute("PRAGMA table_info(absence)")
        absence_columns = [col[1] for col in cursor.fetchall()]
        
        absence_additions = [
            ("cancelled_at", "TEXT"),
            ("cancelled_by_id", "TEXT"),
            ("cancel_reason", "TEXT"),
        ]
        
        for col_name, col_type in absence_additions:
            if col_name not in absence_columns:
                cursor.execute(f"ALTER TABLE absence ADD COLUMN {col_name} {col_type}")
                print(f"Added absence.{col_name}")
        
        # Check and add columns to substitute_request table
        cursor.execute("PRAGMA table_info(substitute_request)")
        subreq_columns = [col[1] for col in cursor.fetchall()]
        
        subreq_additions = [
            ("subject", "TEXT"),
            ("class_name", "TEXT"),
            ("venue_name", "TEXT"),
            ("is_mentor_duty", "INTEGER DEFAULT 0"),
            ("mentor_group_id", "TEXT"),
            ("declined_at", "TEXT"),
            ("declined_by_id", "TEXT"),
            ("decline_reason", "TEXT"),
            ("push_sent_at", "TEXT"),
            ("push_queued_until", "TEXT"),
            ("original_substitute_id", "TEXT"),
        ]
        
        for col_name, col_type in subreq_additions:
            if col_name not in subreq_columns:
                cursor.execute(f"ALTER TABLE substitute_request ADD COLUMN {col_name} {col_type}")
                print(f"Added substitute_request.{col_name}")
        
        conn.commit()
        print("Migration v3 complete!")


if __name__ == "__main__":
    migrate()
