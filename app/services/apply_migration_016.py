"""
Migration 016: Notice<->Schedule link (E-04 notice<->schedule LINK flow).

Adds a single nullable column `linked_source_id` to the `notice` table. This is
a soft foreign key to schedule_source.id (E-05). A notice MAY point at one
published schedule_source so the reader can tap through to that schedule's
original artifact; NULL = a plain notice with no linked schedule (the default
for every existing and future plain notice).

Direction (LOCKED): schedule upstream, notice downstream. The notice merely
references the schedule; it never duplicates the file or the rows. The link is
resolved at read time against published+active sources, so a link to a since-
unpublished or soft-deleted source degrades safely to a plain notice (the JOIN
yields nothing and the card simply drops the affordance).

Not a hard FK: SQLite foreign-key enforcement is off app-wide here, matching the
existing schedule_item.source_id soft-FK convention. Referential consistency is
enforced in the query layer (validate on write against the published set; filter
on read), not by the engine.

Additive + nullable => zero backfill, zero risk to existing rows. Idempotent:
guarded by schema_version = 16 AND a live PRAGMA column check, so re-running on
every boot is a no-op once applied.

Tenant scope: this migration only alters table structure (one ADD COLUMN); it
performs no data writes, so there are no tenant_id-scoping concerns here.
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
        print("Database doesn't exist yet, skipping migration 016")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 16")
    if cursor.fetchone():
        print("Migration 016 already applied")
        conn.close()
        return

    print("Applying migration 016: notice.linked_source_id (notice<->schedule link)...")

    # Add the nullable soft-FK column, guarded by a live PRAGMA check so a
    # re-run (or a hand-applied column) never raises a duplicate-column error.
    cursor.execute("PRAGMA table_info(notice)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    if "linked_source_id" not in existing_cols:
        cursor.execute(
            "ALTER TABLE notice ADD COLUMN linked_source_id TEXT"
        )
        print("Added column notice.linked_source_id")
    else:
        print("Column notice.linked_source_id already exists, skipping ALTER")

    # Record schema version.
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (16, 'E-04 notice<->schedule link: notice.linked_source_id')
    """)

    conn.commit()

    # Verify the column is present and report.
    cursor.execute("PRAGMA table_info(notice)")
    cols_after = [row["name"] for row in cursor.fetchall()]
    if "linked_source_id" in cols_after:
        print("Migration 016 complete! notice.linked_source_id present.")
    else:
        print("WARNING: Migration 016 recorded but notice.linked_source_id NOT found.")

    conn.close()


if __name__ == "__main__":
    apply_migration()
