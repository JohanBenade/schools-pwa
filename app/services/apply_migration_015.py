"""
Migration 015: Schedules & Programmes (E-05 Phase A) - data layer.

Creates the three E-05 tables (the "one-spine schedule archive", spec v0.1):
  - programme        : the controlled list of uploadable programme types
                       (filter chips / lenses). Seeded with the 6 pilot
                       programmes. UUID id + stable slug.
  - schedule_source  : one row per uploaded document (the original pretty
                       picture/PDF + draft/published status, Model B gate).
  - schedule_item    : THE SPINE - one dated row per item. The week-view and
                       school-calendar render from here. Optional time/grade/
                       session/venue/sub_label columns carry the six input
                       shapes (spec section 3.3). Shaped to receive a Phase-2
                       concerns_scope/concerns_ref link later (NOT built now).

Also adds the author capability flag:
  - user_session.can_post_schedule (INTEGER NOT NULL DEFAULT 0), mirroring
    can_post_notice (m013). Seeded for the SAME launch authors as notices:
    all principal + deputy roles by role predicate, plus Delene by her unique
    staff_id (role 'activities', shared by no other launch author). The B-13
    lesson is respected: authors are granted by role predicate / known
    staff_id, never via an account-minting or runtime identity route.

All tables are tenant-scoped from day one (tenant_id NOT NULL; single-tenant
'MARAGON' for the pilot) so a second tenant never inherits S-03 residue debt.

Idempotent: guarded by schema_version = 15. The flag ALTER is guarded by a live
PRAGMA check; the programme seed uses fixed UUID ids + INSERT OR IGNORE so a
re-run never duplicates. All DDL + seed run inside a single explicit
transaction; any failure rolls back and schema_version 15 is NOT recorded.

Bell Times + Days Calendar are deliberately NOT registered as programmes here
(spec section 3.4 decision: reference, do not duplicate - they remain the single
source of truth under the existing Schedule icon).
"""

import sqlite3
from pathlib import Path


# Delene's role ('activities') is shared by no other launch author, so she is
# targeted by her unique staff_id - a one-off seed value, not a runtime identity
# route. Same value as m013 (can_post_notice seed).
DELENE_STAFF_ID = "ba1061df-3968-4fa2-a149-49f4e69084b5"

TENANT_ID = "MARAGON"

# The 6 uploadable programmes for the pilot (spec section 3.1). Fixed UUID ids so
# the seed is idempotent (INSERT OR IGNORE on a stable PK). (name, slug, sort).
PROGRAMMES = [
    ("e05a0001-0000-4000-8000-000000000001", "Monday Assembly",      "monday-assembly",     10),
    ("e05a0002-0000-4000-8000-000000000002", "Friday Mentor",        "friday-mentor",       20),
    ("e05a0003-0000-4000-8000-000000000003", "Academic Deadlines",   "academic-deadlines",  30),
    ("e05a0004-0000-4000-8000-000000000004", "Staff Programme",      "staff-programme",     40),
    ("e05a0005-0000-4000-8000-000000000005", "Assessment Timetable", "assessment-timetable", 50),
    ("e05a0006-0000-4000-8000-000000000006", "Exam Timetable",       "exam-timetable",      60),
]


def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))


def apply_migration():
    db_path = get_db_path()

    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 015")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 15")
    if cursor.fetchone():
        print("Migration 015 already applied")
        conn.close()
        return

    print("Applying migration 015: Schedules & Programmes (E-05 Phase A)...")

    # Everything (3 CREATE TABLEs, the flag ALTER, both seeds, the version
    # record) runs in ONE explicit transaction. Any failure rolls back the whole
    # block and schema_version 15 is never recorded - so a re-run is clean.
    try:
        cursor.execute("BEGIN")

        # --- 1. programme: controlled list (filter chips / lenses) ---------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS programme (
                id          TEXT PRIMARY KEY,
                tenant_id   TEXT NOT NULL,
                name        TEXT NOT NULL,
                slug        TEXT NOT NULL,
                colour      TEXT,
                sort_order  INTEGER NOT NULL DEFAULT 0,
                is_active   INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_programme_tenant ON programme(tenant_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_programme_slug ON programme(slug)"
        )

        # --- 2. schedule_source: one row per uploaded document -------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_source (
                id             TEXT PRIMARY KEY,
                tenant_id      TEXT NOT NULL,
                programme_id   TEXT NOT NULL,
                title          TEXT NOT NULL,
                term_label     TEXT,
                file_path      TEXT,
                file_type      TEXT,
                uploaded_by_id TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'draft',
                posted_at      TEXT NOT NULL,
                published_at   TEXT,
                is_active      INTEGER NOT NULL DEFAULT 1,
                notes          TEXT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedsource_tenant ON schedule_source(tenant_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedsource_programme ON schedule_source(programme_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedsource_status ON schedule_source(status)"
        )

        # --- 3. schedule_item: THE SPINE (many per source) -----------------
        # Phase-2 personalisation will add concerns_scope / concerns_ref off
        # this table - NOT built now, but the spine is shaped to receive it.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_item (
                id            TEXT PRIMARY KEY,
                tenant_id     TEXT NOT NULL,
                source_id     TEXT NOT NULL,
                programme_id  TEXT NOT NULL,
                item_date     TEXT NOT NULL,
                end_date      TEXT,
                start_time    TEXT,
                end_time      TEXT,
                grade         TEXT,
                session       TEXT,
                venue         TEXT,
                label         TEXT NOT NULL,
                sub_label     TEXT,
                sort_hint     INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheditem_tenant ON schedule_item(tenant_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheditem_source ON schedule_item(source_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheditem_programme ON schedule_item(programme_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheditem_date ON schedule_item(item_date)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheditem_active ON schedule_item(is_active)"
        )

        # --- 4. can_post_schedule flag on user_session (mirrors m013) -------
        cursor.execute("PRAGMA table_info(user_session)")
        existing_cols = [row["name"] for row in cursor.fetchall()]
        if "can_post_schedule" not in existing_cols:
            cursor.execute(
                "ALTER TABLE user_session ADD COLUMN can_post_schedule INTEGER NOT NULL DEFAULT 0"
            )
            print("Added column user_session.can_post_schedule")
        else:
            print("Column user_session.can_post_schedule already exists, skipping ALTER")

        # --- 5. Seed the 6 pilot programmes (idempotent on fixed UUID id) ---
        for prog_id, name, slug, sort_order in PROGRAMMES:
            cursor.execute(
                """
                INSERT OR IGNORE INTO programme
                    (id, tenant_id, name, slug, colour, sort_order, is_active)
                VALUES (?, ?, ?, ?, NULL, ?, 1)
                """,
                (prog_id, TENANT_ID, name, slug, sort_order),
            )
        cursor.execute("SELECT COUNT(*) FROM programme WHERE tenant_id = ?", (TENANT_ID,))
        prog_count = cursor.fetchone()[0]
        print(f"Seeded programmes; programme rows for tenant: {prog_count}")

        # --- 6. Seed can_post_schedule for the SAME launch authors as notices
        #    a) all principal + deputy roles (by role predicate)
        cursor.execute(
            "UPDATE user_session SET can_post_schedule = 1 "
            "WHERE role IN ('principal', 'deputy') AND is_active = 1"
        )
        print(f"Seeded can_post_schedule for principal/deputy roles: {cursor.rowcount} rows")

        #    b) Delene by staff_id (role 'activities')
        cursor.execute(
            "UPDATE user_session SET can_post_schedule = 1 "
            "WHERE staff_id = ? AND is_active = 1",
            (DELENE_STAFF_ID,),
        )
        delene_rows = cursor.rowcount
        print(f"Seeded can_post_schedule for Delene (staff_id): {delene_rows} rows")
        if delene_rows == 0:
            print("WARNING: Delene seed matched 0 active rows - she will NOT be able "
                  "to upload schedules. Verify her staff_id / is_active in user_session.")

        # --- 7. Record schema version (only reached if all of the above ran)
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (15, 'E-05 Schedules & Programmes Phase A: programme + schedule_source + schedule_item + can_post_schedule')
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    # Report (post-commit, read-only).
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name IN ('programme', 'schedule_source', 'schedule_item')"
    )
    tables = sorted(r["name"] for r in cursor.fetchall())
    print(f"Migration 015 complete! Tables present: {tables}")

    conn.close()


if __name__ == "__main__":
    apply_migration()
