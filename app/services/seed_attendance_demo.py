"""
Seed attendance data for SchoolOps demo.

Patterns injected:
  1. Baseline ~97% attendance
  2. Chronic absentee cluster (30 learners, ~+10% absence)
  3. Day-of-week effect (Mon/Fri slightly higher absence)
  4. Flu spike 9-13 March 2026 (+9% absence)
  5. Grade variance (Gr 8 +2%, Gr 9 +1%, Gr 12 -1%)
  6. Class outliers (9 SM, 8 NM +4% absence)

Idempotent: refuses to overwrite existing data unless --replace is set.

Usage:
  # Bulk historical seed
  python3 -m app.services.seed_attendance_demo --start 2026-01-14 --end 2026-05-27 --stasy-captured 1

  # Daily top-up (current day, not yet in STASY)
  python3 -m app.services.seed_attendance_demo --date 2026-05-28 --stasy-captured 0

  # Replace existing data in range
  python3 -m app.services.seed_attendance_demo --start 2026-01-14 --end 2026-05-27 --replace
"""
import argparse
import sqlite3
import random
import uuid
from datetime import datetime, date

DB_PATH = '/var/data/schoolops.db'
TENANT_ID = 'MARAGON'

SEED = 4242

BASE_ABSENCE_PROB = 0.012
MONDAY_ADJ = 0.008
FRIDAY_ADJ = 0.05
FLU_START = date(2026, 3, 9)
FLU_END = date(2026, 3, 13)
FLU_ADJ = 0.11
GRADE_ADJUSTMENTS = {8: 0.008, 9: 0.005, 10: 0.0, 11: 0.0, 12: -0.002}
OUTLIER_CLASSES = {'9 SM', '8 NM'}
OUTLIER_ADJ = 0.025
CHRONIC_COUNT = 30
CHRONIC_ADJ = 0.22


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', help='YYYY-MM-DD')
    ap.add_argument('--end', help='YYYY-MM-DD')
    ap.add_argument('--date', help='YYYY-MM-DD (single day shortcut)')
    ap.add_argument('--stasy-captured', type=int, default=1, choices=[0, 1])
    ap.add_argument('--replace', action='store_true')
    args = ap.parse_args()

    if args.date:
        start_d = end_d = datetime.strptime(args.date, '%Y-%m-%d').date()
    elif args.start and args.end:
        start_d = datetime.strptime(args.start, '%Y-%m-%d').date()
        end_d = datetime.strptime(args.end, '%Y-%m-%d').date()
    else:
        ap.error('Provide --date OR both --start and --end')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT date FROM school_calendar
        WHERE tenant_id = ? AND date >= ? AND date <= ? AND is_school_day = 1
        ORDER BY date
    """, (TENANT_ID, start_d.isoformat(), end_d.isoformat()))
    school_days = [r['date'] for r in c.fetchall()]
    if not school_days:
        print(f'No school days in range {start_d} to {end_d} -- aborting')
        return
    print(f'School days: {len(school_days)} ({school_days[0]} -> {school_days[-1]})')

    if args.replace:
        c.execute("""
            DELETE FROM attendance_entry
            WHERE attendance_id IN (
                SELECT id FROM attendance WHERE tenant_id = ? AND date >= ? AND date <= ?
            )
        """, (TENANT_ID, start_d.isoformat(), end_d.isoformat()))
        print(f'  Cleared {c.rowcount} attendance_entry rows')
        c.execute("DELETE FROM attendance WHERE tenant_id = ? AND date >= ? AND date <= ?",
                  (TENANT_ID, start_d.isoformat(), end_d.isoformat()))
        print(f'  Cleared {c.rowcount} attendance rows')
        conn.commit()

    placeholders = ','.join('?' * len(school_days))
    c.execute(f"SELECT COUNT(*) FROM attendance WHERE tenant_id = ? AND date IN ({placeholders})",
              [TENANT_ID] + school_days)
    existing = c.fetchone()[0]
    if existing > 0:
        print(f'ERROR: {existing} attendance rows already exist in range. Use --replace.')
        return

    c.execute("""
        SELECT mg.id, mg.group_name, mg.mentor_id, g.grade_number
        FROM mentor_group mg
        JOIN grade g ON g.id = mg.grade_id
        WHERE mg.tenant_id = ?
        ORDER BY g.grade_number, mg.group_name
    """, (TENANT_ID,))
    mentor_groups = [dict(r) for r in c.fetchall()]
    print(f'Mentor groups: {len(mentor_groups)}')

    c.execute("""
        SELECT id, first_name, surname, mentor_group_id
        FROM learner
        WHERE tenant_id = ? AND is_active = 1
        ORDER BY id
    """, (TENANT_ID,))
    learners = [dict(r) for r in c.fetchall()]
    print(f'Active learners: {len(learners)}')

    learners_by_mg = {}
    for l in learners:
        learners_by_mg.setdefault(l['mentor_group_id'], []).append(l)

    rng_chronic = random.Random(SEED)
    ids = [l['id'] for l in learners]
    rng_chronic.shuffle(ids)
    chronic_set = set(ids[:CHRONIC_COUNT])
    print(f'Chronic absentees: {len(chronic_set)} learners')

    rng = random.Random(SEED + 1)
    now = datetime.now().isoformat()
    captured_at = f"{end_d.isoformat()}T10:30:00" if args.stasy_captured else None
    captured_by = 'Office' if args.stasy_captured else None

    total_att = 0
    total_entries = 0

    for date_str in school_days:
        d = datetime.strptime(date_str, '%Y-%m-%d').date()
        weekday = d.weekday()
        day_adj = MONDAY_ADJ if weekday == 0 else (FRIDAY_ADJ if weekday == 4 else 0.0)
        flu_adj = FLU_ADJ if (FLU_START <= d <= FLU_END) else 0.0

        for mg in mentor_groups:
            outlier_adj = OUTLIER_ADJ if mg['group_name'] in OUTLIER_CLASSES else 0.0
            grade_adj = GRADE_ADJUSTMENTS.get(mg['grade_number'], 0.0)

            sub_h = rng.randint(7, 8)
            sub_m = rng.randint(15, 50) if sub_h == 7 else rng.randint(0, 30)
            submitted_at = f"{date_str}T{sub_h:02d}:{sub_m:02d}:00"

            att_id = str(uuid.uuid4())
            c.execute("""
                INSERT INTO attendance
                (id, tenant_id, date, mentor_group_id, submitted_by_id, submitted_at,
                 status, stasy_captured, stasy_captured_at, stasy_captured_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'Submitted', ?, ?, ?, ?, ?)
            """, (att_id, TENANT_ID, date_str, mg['id'], mg['mentor_id'], submitted_at,
                  args.stasy_captured, captured_at, captured_by, now, now))
            total_att += 1

            for l in learners_by_mg.get(mg['id'], []):
                chronic_adj = CHRONIC_ADJ if l['id'] in chronic_set else 0.0
                prob = BASE_ABSENCE_PROB + day_adj + flu_adj + grade_adj + outlier_adj + chronic_adj
                prob = max(0.0, min(prob, 0.50))

                if rng.random() < prob:
                    status = 'Absent'
                else:
                    status = 'Present'

                c.execute("""
                    INSERT INTO attendance_entry
                    (id, attendance_id, learner_id, status, stasy_captured, stasy_captured_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), att_id, l['id'], status,
                      args.stasy_captured, captured_at, now, now))
                total_entries += 1

        conn.commit()

    print(f'Inserted: {total_att} attendance rows, {total_entries} attendance_entry rows')

    print('Rebuilding learner_absent_tracking...')
    c.execute("DELETE FROM learner_absent_tracking WHERE tenant_id = ?", (TENANT_ID,))
    c.execute("""
        SELECT ae.learner_id, a.date, ae.status
        FROM attendance_entry ae
        JOIN attendance a ON a.id = ae.attendance_id
        WHERE a.tenant_id = ?
        ORDER BY ae.learner_id, a.date DESC
    """, (TENANT_ID,))
    rows = c.fetchall()

    tracking = {}
    for row in rows:
        lid = row['learner_id']
        if lid not in tracking:
            consecutive = 1 if row['status'] == 'Absent' else 0
            tracking[lid] = [consecutive, row['status'], row['date'], (row['status'] == 'Absent')]
        else:
            t = tracking[lid]
            if t[3] and row['status'] == 'Absent':
                t[0] += 1
            else:
                t[3] = False

    for lid, (consec, last_status, last_date, _) in tracking.items():
        c.execute("""
            INSERT OR REPLACE INTO learner_absent_tracking
            (learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (lid, TENANT_ID, consec, last_status, last_date, now))
    conn.commit()
    print(f'  Tracked {len(tracking)} learners')

    c.execute("""
        SELECT
          SUM(CASE WHEN ae.status='Present' THEN 1 ELSE 0 END) AS present,
          SUM(CASE WHEN ae.status='Absent' THEN 1 ELSE 0 END) AS absent,
          COUNT(*) AS total
        FROM attendance_entry ae JOIN attendance a ON a.id = ae.attendance_id
        WHERE a.tenant_id = ?
    """, (TENANT_ID,))
    s = c.fetchone()
    if s['total'] > 0:
        print(f"\nOverall (across all seeded data):")
        print(f"  Present:    {s['present']:>6} ({s['present']/s['total']*100:.1f}%)")
        print(f"  Absent:     {s['absent']:>6} ({s['absent']/s['total']*100:.1f}%)")

    conn.close()


if __name__ == '__main__':
    main()
