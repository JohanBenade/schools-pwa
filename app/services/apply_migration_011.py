"""
Migration 011: learner_subject join table (learner <-> subject enrolment)
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
        print("Database doesn't exist yet, skipping migration 011")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 11")
    if cursor.fetchone():
        print("Migration 011 already applied")
        conn.close()
        return

    print("Applying migration 011: learner_subject join table...")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learner_subject (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            learner_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learner_subject_learner ON learner_subject(learner_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learner_subject_tenant ON learner_subject(tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learner_subject_subject ON learner_subject(subject)")

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (11, 'learner_subject join table for per-period absent view')
    """)

    conn.commit()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='learner_subject'")
    if cursor.fetchone():
        print("Migration 011 complete! learner_subject table confirmed present.")
    else:
        print("WARNING: Migration 011 recorded but learner_subject table NOT found.")

    conn.close()


if __name__ == "__main__":
    apply_migration()
