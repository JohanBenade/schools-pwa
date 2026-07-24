"""
Migration 020: grade INTEGER column on timetable_slot and substitute_request.

WHY
---
Grade existed as a discrete value in the timetable source data
(TIMETABLE_SLOTS tuples: day, period, subject, GRADE, class_code, venue) but
was destroyed at ingest by concatenation into the display string
    class_name = f"Gr{grade} {class_code}"
Downstream consumers therefore had no grade to sort or filter on. The learner
notice (F-3) could only ORDER BY period, leaving ties in undefined order, and
a text sort on class_name orders Gr10, Gr11, Gr12, Gr9 - Gr9 last.

This migration makes grade real data:
  - timetable_slot.grade      INTEGER NULL  (source of truth, set at import)
  - substitute_request.grade  INTEGER NULL  (denormalised at request creation,
                                             matching the existing class_name /
                                             subject / venue_name pattern)

class_name is NOT changed. It remains the human-readable display string.

BACKFILL
--------
Existing rows predate the column, so grade is parsed ONCE here from class_name
using ^Gr(\\d+). This is a one-time data migration, not a read-time parse -
after this, grade is written directly from the source value at ingest and no
string parsing occurs anywhere in the request path.

Verified against the live DB (24 Jul 2026): the distinct leading tokens in
timetable_slot.class_name are exactly Gr8, Gr9, Gr10, Gr11, Gr12. Any row that
does not match the pattern is left NULL and REPORTED by count - never guessed.

Mentor-duty rows (substitute_request.is_mentor_duty = 1) are deliberately
skipped. They carry absence.mentor_class ('12 BD' format), not a timetable
class_name, and the learner notice excludes them (is_mentor_duty = 0).
Parsing that format would reintroduce exactly the string-hack this migration
removes. grade stays NULL there until a real consumer needs it.

SCOPE
-----
The backfill is NOT tenant-filtered. This is a structural data repair, not a
capability grant, so it must correct every row in the table regardless of
tenant. (S-03 tenant isolation applies to reads and grants; a column backfill
that skipped a tenant would leave that tenant's data broken.)

Idempotent: guarded by schema_version = 20; both ALTERs guarded by live PRAGMA
checks; the backfill only touches rows WHERE grade IS NULL. Verify-before-stamp
per the 017 lesson - both columns are re-checked via PRAGMA before
schema_version 20 is recorded; any failure rolls back and the stamp is
withheld, so a re-run is clean.
"""

import re
import sqlite3
from pathlib import Path


COLUMN = "grade"

# Live-verified format: 'Gr9 B', 'Gr10 Key 2', 'Gr12 D'. Anchored at start.
GRADE_RE = re.compile(r"^Gr(\d+)\b")


def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))


def _add_column_if_missing(cursor, table):
    """PRAGMA-guarded ALTER. Returns True if the column was added."""
    cursor.execute("PRAGMA table_info({})".format(table))
    cols = [row["name"] for row in cursor.fetchall()]
    if COLUMN in cols:
        print("Column {}.{} already exists, skipping ALTER".format(table, COLUMN))
        return False
    cursor.execute(
        "ALTER TABLE {} ADD COLUMN grade INTEGER".format(table)
    )
    print("Added column {}.{}".format(table, COLUMN))
    return True


def _backfill(cursor, table, extra_where=""):
    """
    Parse grade from class_name for rows that have none yet.

    Returns (matched, unmatched). Unmatched rows keep grade NULL and are
    reported - never defaulted, never guessed.
    """
    sql = (
        "SELECT id, class_name FROM {} "
        "WHERE grade IS NULL AND class_name IS NOT NULL".format(table)
    )
    if extra_where:
        sql += " AND " + extra_where
    cursor.execute(sql)
    rows = cursor.fetchall()

    updates = []
    unmatched_samples = []
    for row in rows:
        m = GRADE_RE.match(row["class_name"] or "")
        if m:
            updates.append((int(m.group(1)), row["id"]))
        elif len(unmatched_samples) < 5:
            unmatched_samples.append(row["class_name"])

    if updates:
        cursor.executemany(
            "UPDATE {} SET grade = ? WHERE id = ?".format(table), updates
        )

    matched = len(updates)
    unmatched = len(rows) - matched
    print("Backfill {}: {} rows set, {} left NULL".format(
        table, matched, unmatched))
    if unmatched:
        print("  Unmatched class_name samples (grade left NULL): {}".format(
            unmatched_samples))
    return matched, unmatched


def apply_migration():
    db_path = get_db_path()

    if not db_path.exists():
        print("Database doesn't exist yet, skipping migration 020")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT version FROM schema_version WHERE version = 20")
    if cursor.fetchone():
        print("Migration 020 already applied")
        conn.close()
        return

    print("Applying migration 020: grade column + backfill...")

    try:
        cursor.execute("BEGIN")

        # --- 1. ALTERs, each guarded by a live PRAGMA -----------------------
        _add_column_if_missing(cursor, "timetable_slot")
        _add_column_if_missing(cursor, "substitute_request")

        # --- 2. Backfill from class_name (one-time parse) -------------------
        _backfill(cursor, "timetable_slot")
        # Mentor-duty rows excluded by design (see module docstring).
        # COALESCE guards any legacy row where the flag was never set.
        _backfill(cursor, "substitute_request",
                  "COALESCE(is_mentor_duty, 0) = 0")

        # --- 3. Verify BEFORE stamping (the 017 lesson) ---------------------
        for table in ("timetable_slot", "substitute_request"):
            cursor.execute("PRAGMA table_info({})".format(table))
            cols_after = [row["name"] for row in cursor.fetchall()]
            if COLUMN not in cols_after:
                raise RuntimeError(
                    "Verify failed: {}.grade not present after ALTER; "
                    "withholding schema_version 20.".format(table)
                )

        # --- 4. Record schema version (only reached if all above ran) -------
        cursor.execute("""
            INSERT OR IGNORE INTO schema_version (version, description)
            VALUES (20, 'grade INTEGER on timetable_slot + substitute_request, backfilled from class_name')
        """)

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    # Report (post-commit, read-only).
    cursor.execute(
        "SELECT COUNT(*) FROM substitute_request "
        "WHERE grade IS NULL AND COALESCE(is_mentor_duty, 0) = 0"
    )
    orphan_requests = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM timetable_slot WHERE grade IS NULL")
    orphan_slots = cursor.fetchone()[0]

    print("Migration 020 complete!")
    print("  timetable_slot rows still NULL grade: {}".format(orphan_slots))
    print("  non-mentor substitute_request rows still NULL grade: {}".format(
        orphan_requests))
    if orphan_slots or orphan_requests:
        print("  NOTE: NULL grades sort LAST in the learner notice by design.")

    conn.close()


if __name__ == "__main__":
    apply_migration()
