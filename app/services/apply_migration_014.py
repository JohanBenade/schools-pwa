"""
Migration 014: Notice Board (E-04) - make image_path nullable.

E-04 Phase C decision (Johan, S127): a notice must support image-only, PDF-only,
AND text-only posts (text-only = a management broadcast with no attachment, same
as a WhatsApp/email message). The Phase A/013 schema created image_path as
NOT NULL (image-first). To allow text-only and PDF-only notices, image_path must
become nullable.

SQLite cannot ALTER a column to drop NOT NULL in place, so this migration does a
standard safe table rebuild:
  1. CREATE notice_new (identical to notice, but image_path TEXT nullable)
  2. INSERT ... SELECT all rows from notice -> notice_new
  3. DROP notice
  4. ALTER TABLE notice_new RENAME TO notice
  5. recreate the 3 indexes (tenant, category, active)

The new validity rule (title + category + at least one of body/image/pdf) is
enforced in the route handler, NOT at the schema level - the schema only needs to
permit a NULL image_path. The other NOT NULL columns are unchanged.

Idempotent: guarded by schema_version = 14, AND re-checks the live column
nullability so a partial/re-run is safe. Tenant scope unchanged (single-tenant;
S-03 gating checklist owns multi-tenant scoping).
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
        print("Database doesn't exist yet, skipping migration 014")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 14")
    if cursor.fetchone():
        print("Migration 014 already applied")
        conn.close()
        return

    # Defensive: if the notice table doesn't exist (013 not yet run), skip.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notice'")
    if not cursor.fetchone():
        print("notice table not present yet, skipping migration 014 (013 must run first)")
        conn.close()
        return

    # If image_path is already nullable, just record the version and stop.
    cursor.execute("PRAGMA table_info(notice)")
    image_col = next((r for r in cursor.fetchall() if r["name"] == "image_path"), None)
    if image_col is not None and image_col["notnull"] == 0:
        print("image_path already nullable - recording schema_version 14, no rebuild needed")
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (14, 'E-04 Notice Board: image_path nullable (text-only/PDF-only notices)')
        """)
        conn.commit()
        conn.close()
        return

    print("Applying migration 014: making notice.image_path nullable (table rebuild)...")

    # The rebuild (create -> copy -> drop -> rename -> reindex) is wrapped in a
    # single explicit transaction. If the process dies mid-rebuild, the whole
    # block rolls back and the ORIGINAL `notice` table survives intact - there is
    # never a committed window where `notice` is dropped but un-renamed.
    try:
        cursor.execute("BEGIN")

        # 1. New table - identical to live notice, but image_path is TEXT (nullable).
        cursor.execute("""
            CREATE TABLE notice_new (
                id              TEXT PRIMARY KEY,
                tenant_id       TEXT NOT NULL,
                title           TEXT NOT NULL,
                body            TEXT,
                category        TEXT NOT NULL,
                image_path      TEXT,
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

        # 2. Copy every row (explicit column list - order-safe). All rows,
        #    including is_active = 0 (soft-deleted) - correct for a rebuild.
        cursor.execute("""
            INSERT INTO notice_new (
                id, tenant_id, title, body, category, image_path,
                attachment_path, attachment_type, posted_by_id, author_desk,
                is_pinned, notify_sent, posted_at, is_active
            )
            SELECT
                id, tenant_id, title, body, category, image_path,
                attachment_path, attachment_type, posted_by_id, author_desk,
                is_pinned, notify_sent, posted_at, is_active
            FROM notice
        """)
        copied = cursor.rowcount
        print(f"Copied {copied} notice row(s) into rebuilt table")

        # 3 + 4. Swap tables.
        cursor.execute("DROP TABLE notice")
        cursor.execute("ALTER TABLE notice_new RENAME TO notice")

        # 5. Recreate the 3 named indexes (verified live: only these 3 named
        #    indexes exist; sqlite_autoindex for the PK is rebuilt by SQLite).
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_tenant ON notice(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_category ON notice(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notice_active ON notice(is_active)")

        # Verify the rebuild succeeded BEFORE committing: image_path must now be
        # nullable. If it is not, roll the whole rebuild back and raise - this
        # ensures a failed rebuild is NEVER recorded as success in schema_version
        # (a re-run will then retry cleanly against the intact original table).
        cursor.execute("PRAGMA table_info(notice)")
        post = next((r for r in cursor.fetchall() if r["name"] == "image_path"), None)
        if post is None or post["notnull"] != 0:
            conn.rollback()
            conn.close()
            raise RuntimeError(
                "Migration 014 rebuild did not yield a nullable image_path; "
                "rolled back, schema_version NOT recorded."
            )

        # Record schema version inside the same transaction (only reached once
        # the rebuild is verified correct).
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (14, 'E-04 Notice Board: image_path nullable (text-only/PDF-only notices)')
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    # Rebuild already verified + committed inside the transaction above. Report.
    cursor.execute("SELECT COUNT(*) FROM notice")
    total = cursor.fetchone()[0]
    print(f"Migration 014 complete! image_path is now nullable; {total} row(s) preserved.")

    conn.close()


if __name__ == "__main__":
    apply_migration()
