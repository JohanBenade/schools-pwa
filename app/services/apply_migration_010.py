"""
Migration 010: Add pointer_before column to absence table.

Stores the substitute-rotation pointer value as it was BEFORE this absence
was processed. On cancellation (early_return / mark_back) the pointer is
restored to this value, so released subs go back in line for the next absence.
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
        print("Database doesn't exist yet, skipping migration 010")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 10")
    if cursor.fetchone():
        print("Migration 010 already applied")
        conn.close()
        return

    print("Applying migration 010: absence.pointer_before...")

    cursor.execute("PRAGMA table_info(absence)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    if "pointer_before" not in existing_cols:
        cursor.execute("ALTER TABLE absence ADD COLUMN pointer_before TEXT")
        print("Added column absence.pointer_before")
    else:
        print("Column absence.pointer_before already exists, skipping ALTER")

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (10, 'absence.pointer_before for pointer restore on cancel')
    """)

    conn.commit()
    conn.close()
    print("Migration 010 complete!")


if __name__ == "__main__":
    apply_migration()
