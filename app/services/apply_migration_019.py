"""
Migration 019: can_share_learner_notice capability flag (E-04/substitute ops).

Adds a per-user capability on user_session:
  - user_session.can_share_learner_notice (INTEGER NOT NULL DEFAULT 0),
    mirroring can_post_notice (m013) and can_post_schedule (m015).

Grants access to /substitute/learner-notice (the Teams copy/paste page) for
users OUTSIDE the role gate. The route's role gate (principal / deputy /
office / admin) is unchanged and remains the primary grant for management and
admin; this flag exists for named individuals with role 'teacher' who run the
substitute-notice workflow.

Seeded for exactly one launch user:
  - Ms Nonhlanhla (Maswanganyi), role 'teacher', by her unique staff_id.
    B-13 respected: granted via a one-off parametrised seed on a verified
    staff_id (read live 24 Jul 2026), never via an account-minting or runtime
    identity route.

The seed UPDATE is tenant-filtered (tenant_id = 'MARAGON') per S-03 isolation
patterns.

Idempotent: guarded by schema_version = 19; the ALTER is guarded by a live
PRAGMA check. Verify-before-stamp per the 017 lesson: the column's existence
is re-checked via PRAGMA before schema_version 19 is recorded; any failure
rolls back and the stamp is withheld, so a re-run is clean.
"""

import sqlite3
from pathlib import Path


# Ms Nonhlanhla's unique staff_id (user_session read, Render live DB,
# 24 Jul 2026: display_name 'Ms Nonhlanhla', role 'teacher', is_active 1).
NONI_STAFF_ID = "abe4a9dd-ff2f-4bfa-934d-900fc7f14562"

TENANT_ID = "MARAGON"

COLUMN = "can_share_learner_notice"


def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))


def apply_migration():
    db_path = get_db_path()

    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 019")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 19")
    if cursor.fetchone():
        print("Migration 019 already applied")
        conn.close()
        return

    print("Applying migration 019: can_share_learner_notice flag...")

    try:
        cursor.execute("BEGIN")

        # --- 1. Flag ALTER, guarded by live PRAGMA (mirrors m015 step 4) ---
        cursor.execute("PRAGMA table_info(user_session)")
        existing_cols = [row["name"] for row in cursor.fetchall()]
        if COLUMN not in existing_cols:
            cursor.execute(
                "ALTER TABLE user_session "
                "ADD COLUMN can_share_learner_notice INTEGER NOT NULL DEFAULT 0"
            )
            print("Added column user_session.can_share_learner_notice")
        else:
            print("Column user_session.can_share_learner_notice already "
                  "exists, skipping ALTER")

        # --- 2. Seed Ms Nonhlanhla by staff_id (tenant-filtered) -----------
        cursor.execute(
            "UPDATE user_session SET can_share_learner_notice = 1 "
            "WHERE staff_id = ? AND tenant_id = ? AND is_active = 1",
            (NONI_STAFF_ID, TENANT_ID),
        )
        noni_rows = cursor.rowcount
        print(f"Seeded can_share_learner_notice for Ms Nonhlanhla "
              f"(staff_id): {noni_rows} rows")
        if noni_rows == 0:
            print("WARNING: Nonhlanhla seed matched 0 active rows - she will "
                  "NOT see the learner notice page. Verify her staff_id / "
                  "is_active in user_session.")

        # --- 3. Verify BEFORE stamping (the 017 lesson) --------------------
        cursor.execute("PRAGMA table_info(user_session)")
        cols_after = [row["name"] for row in cursor.fetchall()]
        if COLUMN not in cols_after:
            raise RuntimeError(
                "Verify failed: user_session.can_share_learner_notice not "
                "present after ALTER; withholding schema_version 19."
            )

        # --- 4. Record schema version (only reached if all above ran) ------
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (19, 'can_share_learner_notice flag on user_session + Nonhlanhla seed')
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    # Report (post-commit, read-only).
    cursor.execute(
        "SELECT COUNT(*) FROM user_session "
        "WHERE can_share_learner_notice = 1 AND tenant_id = ?",
        (TENANT_ID,),
    )
    granted = cursor.fetchone()[0]
    print(f"Migration 019 complete! Users with can_share_learner_notice: "
          f"{granted}")

    conn.close()


if __name__ == "__main__":
    apply_migration()
