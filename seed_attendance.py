#!/usr/bin/env python3
# seed_attendance.py -- ONE-TIME attendance back-fill seeder for SchoolOps.
# AUTO forward-fill from MAX(attendance.date) through today (SAST), academic days only.
# Excludes 12 BD (test group). Idempotent: skips (group,date) already present.
# Mix ~94% Present / 5% Absent / 1% Late, seeded RNG (reproducible).
# Single transaction, asserts counts before commit. DELETE THIS FILE post-pilot.
import sqlite3, uuid, random, datetime

DB = '/var/data/schoolops.db'
TENANT = 'MARAGON'
EXCLUDE_GROUP_ID = 'aa35cfcc-632b-4ed2-aebd-d42074112f29'  # 12 BD - left unmarked for testing
ABSENT_RATE, LATE_RATE = 0.05, 0.01

def uid():
    return str(uuid.uuid4())

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

sast = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
now = sast.replace(tzinfo=None).isoformat()
today = sast.date().isoformat()
anchor = cur.execute("SELECT MAX(date) FROM attendance").fetchone()[0] or '0000-01-01'
print(f"Last seeded date: {anchor}   Today (SAST): {today}")

# Academic days strictly after anchor, up to and including today.
days = [r['date'] for r in cur.execute(
    "SELECT date FROM school_calendar "
    "WHERE date > ? AND date <= ? AND is_school_day = 1 "
    "ORDER BY date", (anchor, today)).fetchall()]
# Idempotent: drop any date that already has attendance rows.
days = [d for d in days if cur.execute(
    "SELECT COUNT(*) FROM attendance WHERE date = ?", (d,)).fetchone()[0] == 0]
if not days:
    print("Already current - nothing to seed.")
    conn.close()
    raise SystemExit(0)
print(f"Seeding {len(days)} academic day(s): {days}")
random.seed(int(days[0].replace('-', '')))

# Load groups (12 BD excluded), then learners per group.
all_groups = cur.execute(
    "SELECT COUNT(*) FROM mentor_group WHERE tenant_id = ?", (TENANT,)).fetchone()[0]
groups = cur.execute(
    "SELECT id, mentor_id FROM mentor_group WHERE tenant_id = ? AND id != ?",
    (TENANT, EXCLUDE_GROUP_ID)).fetchall()
assert len(groups) == all_groups - 1, (
    f"Expected exactly one group (12 BD) excluded: {all_groups} total, "
    f"{len(groups)} after exclude")

lbg, total = {}, 0
for g in groups:
    rows = cur.execute(
        "SELECT id FROM learner WHERE tenant_id = ? AND mentor_group_id = ? AND is_active = 1",
        (TENANT, g['id'])).fetchall()
    lbg[g['id']] = [r['id'] for r in rows]
    total += len(rows)
print(f"{len(groups)} groups (12 BD excluded), {total} active learners")

# Seed. Track final status per learner for the rollup.
hdr = ent = 0
tally = {'Present': 0, 'Absent': 0, 'Late': 0}
final = {}  # learner_id -> (last_status, last_date, trailing_absent_streak)

for d in days:
    submitted_at = f"{d}T09:55:00"
    for g in groups:
        aid = uid()
        cur.execute(
            "INSERT INTO attendance "
            "(id, tenant_id, date, mentor_group_id, submitted_by_id, submitted_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'Submitted')",
            (aid, TENANT, d, g['id'], g['mentor_id'], submitted_at))
        hdr += 1
        for lid in lbg[g['id']]:
            r = random.random()
            if r < ABSENT_RATE:
                st = 'Absent'
            elif r < ABSENT_RATE + LATE_RATE:
                st = 'Late'
            else:
                st = 'Present'
            cur.execute(
                "INSERT INTO attendance_entry (id, attendance_id, learner_id, status) "
                "VALUES (?, ?, ?, ?)",
                (uid(), aid, lid, st))
            ent += 1
            tally[st] += 1
            prev = final.get(lid)
            streak = (prev[2] if prev else 0) + 1 if st == 'Absent' else 0
            final[lid] = (st, d, streak)

# Rollup: one INSERT OR REPLACE per learner with the final seeded date's status.
roll = 0
for lid, (st, d, streak) in final.items():
    cur.execute(
        "INSERT OR REPLACE INTO learner_absent_tracking "
        "(learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (lid, TENANT, streak, st, d, now))
    roll += 1

# Asserts before commit.
exp_hdr = len(groups) * len(days)
exp_ent = total * len(days)
assert hdr == exp_hdr, f"header count {hdr} != expected {exp_hdr}"
assert ent == exp_ent, f"entry count {ent} != expected {exp_ent}"
assert roll == total, f"rollup count {roll} != expected {total}"
pct = {k: round(100 * v / ent, 1) for k, v in tally.items()}
print(f"Headers: {hdr}  Entries: {ent}  Rollup rows: {roll}")
print(f"Mix: {tally}  => {pct}")

conn.commit()
conn.close()
print("COMMITTED. Seed complete.")
