"""
Migration 018: assignment_relocation table (learners-move engine, step a).

One row per substitute_request that involves a physical relocation, recording
the DIRECTION ('LEARNERS_MOVE' | 'SUB_MOVES') and the DESTINATION room.
Kept separate from substitute_request (25 live cols, PRAGMA-verified: no
direction/destination fields) so the relocation concern is isolated and
multi-tenant-clean.

Design (locked in the v151 architecture session):
  - 1:1 with substitute_request, enforced by ux_reloc_request unique index.
    Reassign/decline flows REPLACE the row, never accumulate.
  - direction stored explicitly even for SUB_MOVES (readers never re-derive
    intent).
  - destination_venue_id: LEARNERS_MOVE -> sub's home room (staff_venue);
    SUB_MOVES -> absent teacher's room.
  - destination_venue_code denormalised for notice render (no join), same
    pattern as substitute_request.venue_name.
  - ON DELETE CASCADE from substitute_request (FKs are enforced live:
    PRAGMA foreign_keys = ON in get_connection). Absence deletion cascades
    absence -> substitute_request -> assignment_relocation.
  - Rows are written ONLY for assigned requests (R10); Pending writes none.

Additive only. Idempotent: safe to run repeatedly. Guarded on
schema_version = 18. Verify-before-stamp per the 017 lesson (SQLite
auto-commits DDL; safety = idempotent DDL + withholding the stamp).
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
        print("Database doesn't exist yet, skipping migration 018")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 18")
    if cursor.fetchone():
        print("Migration 018 already applied")
        conn.close()
        return

    print("Applying migration 018: assignment_relocation table...")

    # --- 1. Table (locked DDL) ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assignment_relocation (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            substitute_request_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            destination_venue_id TEXT NOT NULL,
            destination_venue_code TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (substitute_request_id)
                REFERENCES substitute_request(id) ON DELETE CASCADE,
            FOREIGN KEY (destination_venue_id) REFERENCES venue(id)
        )
    """)

    # --- 2. Indexes ---
    # 1:1 guard: one relocation row per request, ever.
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_reloc_request
        ON assignment_relocation(substitute_request_id)
    """)
    # Tenant index per S-03 isolation patterns (matches idx_house_tenant in 017).
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reloc_tenant
        ON assignment_relocation(tenant_id)
    """)

    # --- Self-verify BEFORE stamping schema_version ---
    ok = True

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assignment_relocation'")
    if not cursor.fetchone():
        print("WARNING: assignment_relocation table NOT found during migration 018.")
        ok = False
    else:
        cursor.execute("PRAGMA table_info(assignment_relocation)")
        cols = {row[1] for row in cursor.fetchall()}
        expected = {"id", "tenant_id", "substitute_request_id", "direction",
                    "destination_venue_id", "destination_venue_code", "created_at"}
        missing = expected - cols
        if missing:
            print(f"WARNING: assignment_relocation missing columns: {sorted(missing)}")
            ok = False

    for idx in ("ux_reloc_request", "idx_reloc_tenant"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (idx,))
        if not cursor.fetchone():
            print(f"WARNING: {idx} index NOT found during migration 018.")
            ok = False

    if not ok:
        # Not stamped -> next boot retries the idempotent DDL and re-verifies.
        print("Migration 018 FAILED verification - NOT recorded. Will retry next boot.")
        conn.close()
        return

    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (18, 'assignment_relocation: direction + destination per assigned substitute_request (learners-move)')
    """)
    conn.commit()
    if cursor.rowcount == 1:
        print("Migration 018 complete! assignment_relocation table + indexes confirmed.")
    else:
        print("WARNING: migration 018 objects present but schema_version row not inserted "
              "(rowcount=%s). Investigate before relying on version stamp." % cursor.rowcount)

    conn.close()


if __name__ == "__main__":
    apply_migration()
