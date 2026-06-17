"""
Migration 012: Add is_active column to user_session table.

Provides a revocation kill-switch for magic-code logins. is_active defaults
to 1 (active) so all existing sessions remain valid on deploy. Auth lookups
(handle_magic_link, login_code) gain an "AND us.is_active = 1" guard so a
revoked code returns no row and grants no session. A departed staff member's
code can be disabled by setting is_active = 0.
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
        print("Database doesn't exist yet, skipping migration 012")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 12")
    if cursor.fetchone():
        print("Migration 012 already applied")
        conn.close()
        return

    print("Applying migration 012: user_session.is_active...")

    cursor.execute("PRAGMA table_info(user_session)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    if "is_active" not in existing_cols:
        cursor.execute("ALTER TABLE user_session ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        print("Added column user_session.is_active")
    else:
        print("Column user_session.is_active already exists, skipping ALTER")

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (12, 'user_session.is_active revocation kill-switch')
    """)

    conn.commit()
    conn.close()
    print("Migration 012 complete!")


if __name__ == "__main__":
    apply_migration()
