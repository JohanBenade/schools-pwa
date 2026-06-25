"""
Migration 013: Notice Board (E-04) data layer.

Creates the `notice` table (image-first bulletin board, tenant-scoped) and adds
the `can_post_notice` capability flag to user_session (alongside can_resolve /
is_active). Seeds can_post_notice = 1 for the launch authors:
  - by role: every 'principal' and 'deputy' (Pierre + Kea + Marie-Louise + Janine)
  - by staff_id: Delene (role 'activities', Sport/Extra-Mural author)

Schema is image-first with optional body + optional single PDF attachment
(spec v0.4 decisions #9-#12). All new notice columns that are optional are
nullable. Idempotent: guarded by schema_version = 13 and PRAGMA checks.

Tenant scope: SchoolOps is single-tenant (MARAGON) today; per the S-03 sweep
decision (document, do not patch pre-pilot) the seed UPDATEs are not tenant_id-
scoped, matching every sibling migration. user_session is single-tenant, so the
role/staff_id predicates target the correct rows. tenant_id scoping on these
writes is on the S-03 multi-tenant gating checklist (before tenant #2 onboards).
"""

import sqlite3
from pathlib import Path


def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))


# Delene's real staff_id (verified live, S125). Role is 'activities', so she is
# NOT caught by the principal/deputy role seed and must be set explicitly.
DELENE_STAFF_ID = "ba1061df-3968-4fa2-a149-49f4e69084b5"


def apply_migration():
    db_path = get_db_path()

    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 013")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 13")
    if cursor.fetchone():
        print("Migration 013 already applied")
        conn.close()
        return

    print("Applying migration 013: Notice Board (notice table + can_post_notice)...")

    # 1. notice table (tenant-scoped from day one; image-first + optional body/PDF)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notice (
            id              TEXT PRIMARY KEY,
            tenant_id       TEXT NOT NULL,
            title           TEXT NOT NULL,
            body            TEXT,
            category        TEXT NOT NULL,
            image_path      TEXT NOT NULL,
            attachment_path TEXT,
            attachment_type TEXT,
            posted_by_id    TEXT NOT NULL,
            author_desk     TEXT NOT NULL,
            is_pinned       INTEGER NOT NULL DEFAULT 0,
            notify_sent     INTEGER NOT NULL DEFAULT 0,
            posted_at       TEXT NOT NULL,
            is_active       INTEGER NOT NULL DEFAULT 1
        )
    """)

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_tenant ON notice(tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_category ON notice(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_active ON notice(is_active)")

    # 2. can_post_notice flag on user_session (guarded, mirrors can_resolve)
    cursor.execute("PRAGMA table_info(user_session)")
    existing_cols = [row["name"] for row in cursor.fetchall()]
    if "can_post_notice" not in existing_cols:
        cursor.execute(
            "ALTER TABLE user_session ADD COLUMN can_post_notice INTEGER NOT NULL DEFAULT 0"
        )
        print("Added column user_session.can_post_notice")
    else:
        print("Column user_session.can_post_notice already exists, skipping ALTER")

    # 3. Seed launch authors.
    #    Roles are seeded by role predicate (not by baked magic_code) - the B-13
    #    lesson (no account-minting/identity routes) is respected. Delene is the
    #    single exception: her role 'activities' is shared by no other launch
    #    author, so she is targeted by her unique staff_id. This is a one-off
    #    seed value, not a runtime identity route.
    #    a) all principal + deputy roles
    cursor.execute(
        "UPDATE user_session SET can_post_notice = 1 WHERE role IN ('principal', 'deputy')"
    )
    print(f"Seeded can_post_notice for principal/deputy roles: {cursor.rowcount} rows")

    #    b) Delene by staff_id (role 'activities')
    cursor.execute(
        "UPDATE user_session SET can_post_notice = 1 WHERE staff_id = ?",
        (DELENE_STAFF_ID,),
    )
    print(f"Seeded can_post_notice for Delene (staff_id): {cursor.rowcount} rows")

    # 4. Record schema version
    cursor.execute("""
        INSERT OR IGNORE INTO schema_version (version, description)
        VALUES (13, 'E-04 Notice Board: notice table + can_post_notice flag')
    """)

    conn.commit()

    # Verify table present + report seed count
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notice'")
    if cursor.fetchone():
        cursor.execute("SELECT COUNT(*) FROM user_session WHERE can_post_notice = 1")
        seeded = cursor.fetchone()[0]
        print(f"Migration 013 complete! notice table present; {seeded} authors flagged.")
    else:
        print("WARNING: Migration 013 recorded but notice table NOT found.")

    conn.close()


if __name__ == "__main__":
    apply_migration()
