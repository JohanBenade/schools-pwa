"""
Migration 017: Learner import-readiness.

Prepares the schema for the real Maragon learner import (replacing the 625
test rows). Per the data request sent to Kea, each learner carries an
admin/learner number (the refresh key), a preferred/known-as name, gender,
and optional date of birth. House is referenced by learner.house_id but had
no target table; this migration creates it.

All changes are ADDITIVE:
  - Four new nullable columns on `learner` (existing rows untouched).
  - A partial UNIQUE index on (tenant_id, admin_number) so the real import
    can UPSERT cleanly on admin number, while the existing test rows (which
    have NULL admin_number) do not collide.
  - A new `house` table mirroring `grade` (house_name, sort_order, synced_at;
    no is_active - houses are a fixed lookup with no soft-delete lifecycle).

Nothing existing is altered or removed. Idempotent: safe to run repeatedly.
Guarded on schema_version = 17.
"""

import sqlite3
from pathlib import Path


def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))


def _column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def apply_migration():
    db_path = get_db_path()

    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 017")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 17")
    if cursor.fetchone():
        print("Migration 017 already applied")
        conn.close()
        return

    print("Applying migration 017: learner import-readiness fields + house table...")

    # --- 1. Additive columns on learner (guarded so a partial prior run is safe) ---
    for col in ("admin_number", "preferred_name", "gender", "dob"):
        if not _column_exists(cursor, "learner", col):
            cursor.execute(f"ALTER TABLE learner ADD COLUMN {col} TEXT")
            print(f"  added learner.{col}")
        else:
            print(f"  learner.{col} already present, skipped")

    # --- 2. Partial unique index: clean UPSERT key for the real import ---
    # WHERE admin_number IS NOT NULL lets the existing test rows (NULL key)
    # coexist without violating uniqueness.
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_learner_admin
        ON learner(tenant_id, admin_number)
        WHERE admin_number IS NOT NULL
    """)

    # --- 3. house table (mirrors grade's shape exactly; learner.house_id targets it) ---
    # grade columns (PRAGMA-verified live): id, tenant_id, <name>, <code>?,
    # <number>?, sort_order, synced_at. house is a small fixed lookup set with
    # no soft-delete lifecycle, so it follows grade: synced_at (nullable), no
    # is_active. name + sort_order are the only house-specific fields needed.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS house (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            house_name TEXT NOT NULL,
            sort_order INTEGER,
            synced_at TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_house_tenant ON house(tenant_id)")
    # Unique guard: house is resolved by name during import, so prevent
    # duplicate houses per tenant (mirrors why ux_learner_admin exists).
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_house_name
        ON house(tenant_id, house_name)
    """)

    # NOTE: house rows are intentionally NOT seeded here. The Maragon house
    # names are not yet confirmed. A follow-up seed populates them once known;
    # the importer resolves learner house text -> house.id against those rows.

    # --- Self-verify BEFORE stamping schema_version ---
    # SQLite auto-commits DDL under the default isolation level, so the ALTERs
    # and CREATEs above are already durable and cannot be rolled back. The
    # safety mechanism is therefore: (a) all DDL is idempotent (guarded ALTER,
    # CREATE ... IF NOT EXISTS), and (b) we stamp version=17 ONLY after every
    # object is confirmed present. If verify fails we do NOT stamp, so the next
    # boot re-runs the (harmless, idempotent) DDL and re-verifies until it
    # succeeds. Stamping before verifying would mark a broken migration as
    # applied and skip it forever.
    ok = True
    for col in ("admin_number", "preferred_name", "gender", "dob"):
        if not _column_exists(cursor, "learner", col):
            print(f"WARNING: learner.{col} NOT found during migration 017.")
            ok = False

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='house'")
    if not cursor.fetchone():
        print("WARNING: house table NOT found during migration 017.")
        ok = False

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ux_learner_admin'")
    if not cursor.fetchone():
        print("WARNING: ux_learner_admin index NOT found during migration 017.")
        ok = False

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='ux_house_name'")
    if not cursor.fetchone():
        print("WARNING: ux_house_name index NOT found during migration 017.")
        ok = False

    if not ok:
        # Not stamped -> next boot retries the idempotent DDL and re-verifies.
        print("Migration 017 FAILED verification - NOT recorded. Will retry next boot.")
        conn.close()
        return

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (17, 'learner import-readiness: admin_number/preferred_name/gender/dob + house table')
    """)
    conn.commit()
    # The version=17 guard at the top guarantees this row did not exist, so the
    # insert must have taken effect. rowcount confirms it rather than assuming.
    if cursor.rowcount == 1:
        print("Migration 017 complete! learner fields + house table + indexes confirmed.")
    else:
        print("WARNING: migration 017 objects present but schema_version row not inserted "
              "(rowcount=%s). Investigate before relying on version stamp." % cursor.rowcount)

    conn.close()


if __name__ == "__main__":
    apply_migration()
