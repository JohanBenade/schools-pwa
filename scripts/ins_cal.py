import sqlite3, uuid
from datetime import datetime, timezone

DB = "/var/data/schoolops.db"
TENANT = "MARAGON"
KEA = "0f9674b4-2cdf-438b-b960-48bfedd4be61"
now = datetime.now(timezone.utc).isoformat()

PROG_SLUG = "school-calendar"
PROG_NAME = "School Calendar"
PROG_COLOUR = "#4B5563"   # slate grey - neutral, distinct from all 7 existing chips
PROG_SORT = 5             # sort ahead of others: it's the general spine
SRC_TITLE = "Term 3 2026 School Calendar"
SRC_TERM = "Term 3 2026"

# (item_date, end_date, label)
rows = [
    ("2026-07-20", None, "All Staff Back at School"),
    ("2026-07-21", None, "Start of Term 3"),
    ("2026-07-23", None, "City Youth"),
    ("2026-07-26", None, "Grade 12 Drama Excursion - Market Theatre"),
    ("2026-07-30", None, "Student Led Conferences"),
    ("2026-08-01", None, "Grade 12 Hospitality Final Restaurant"),
    ("2026-08-03", "2026-08-07", "Prayer Week"),
    ("2026-08-03", None, "Student Social Media Talk During the School Day"),
    ("2026-08-03", None, "Parent Information Evening - Social Media Presentation"),
    ("2026-08-06", None, "Grade 9 Subject Application Evening"),
    ("2026-08-07", None, "Grade 12 Matric Dance"),
    ("2026-08-12", None, "Big Sweat"),
    ("2026-08-13", None, "City Youth"),
    ("2026-08-14", None, "Blood Drive"),
    ("2026-08-14", None, "SC 2026/2027 Voting"),
    ("2026-08-15", None, "SC Farewell Function"),
    ("2026-08-17", "2026-08-21", "Care Week"),
    ("2026-08-17", None, "SC 2026/2027 Announcement"),
    ("2026-08-20", None, "City Youth"),
    ("2026-08-21", None, "SC Outreach"),
    ("2026-08-22", None, "SC Planning Day"),
    ("2026-08-24", None, "Applicants for Head Leader Q&A with Teachers"),
    ("2026-08-25", None, "Applicants for Head Leader Mini Sweat with Management"),
    ("2026-08-27", None, "City Youth"),
    ("2026-08-28", "2026-08-30", "SC Camp"),
    ("2026-08-29", None, "Grade 10 Hospitality Breakfast"),
    ("2026-08-31", "2026-09-04", "Biodiversity & Arbor Week"),
    ("2026-09-03", None, "Announcement of Head Leaders and Inauguration"),
    ("2026-09-03", None, "City Youth"),
    ("2026-09-04", None, "Arbor Day Tree Planting"),
    ("2026-09-04", None, "Spring Day Civies"),
    ("2026-09-04", None, "Spring Bash"),
    ("2026-09-05", None, "Open Day"),
    ("2026-09-10", None, "City Youth"),
    ("2026-09-11", None, "Grade 11 Teachers High Tea - Rec Time"),
    ("2026-09-17", None, "Culture Day"),
    ("2026-09-17", "2026-09-19", "Isizulu Heritage Trip to KZN"),
    ("2026-09-17", None, "City Youth"),
    ("2026-09-23", None, "Worthy Woman"),
    ("2026-09-23", None, "Mighty Man"),
]
assert len(rows) == 40, "expected 40 rows, got %d" % len(rows)

c = sqlite3.connect(DB)
cur = c.cursor()

row = cur.execute("SELECT id FROM programme WHERE slug=? AND tenant_id=?", (PROG_SLUG, TENANT)).fetchone()
if row:
    prog_id = row[0]; print("programme exists:", prog_id)
else:
    prog_id = str(uuid.uuid4())
    cur.execute("INSERT INTO programme (id,tenant_id,name,slug,colour,sort_order,is_active) VALUES (?,?,?,?,?,?,1)",
                (prog_id, TENANT, PROG_NAME, PROG_SLUG, PROG_COLOUR, PROG_SORT))
    print("programme inserted:", prog_id)

row = cur.execute("SELECT id FROM schedule_source WHERE title=? AND programme_id=? AND tenant_id=? AND is_active=1",
                  (SRC_TITLE, prog_id, TENANT)).fetchone()
if row:
    print("source exists, aborting to avoid dupes:", row[0]); c.close(); raise SystemExit
src_id = str(uuid.uuid4())
cur.execute("INSERT INTO schedule_source (id,tenant_id,programme_id,title,term_label,file_path,file_type,uploaded_by_id,status,posted_at,published_at,is_active,notes) "
            "VALUES (?,?,?,?,?,NULL,NULL,?,'published',?,?,1,?)",
            (src_id, TENANT, prog_id, SRC_TITLE, SRC_TERM, KEA, now, now,
             "Hand-entered from Kea's Term 3 Calendar (Jul-Sep 2026). Assessments + sports excluded (separate calendars). Monthly-updated source; supersede on next distribution."))
print("source inserted:", src_id)

n = 0
for i, (d, ed, label) in enumerate(sorted(rows, key=lambda x:(x[0], x[2]))):
    cur.execute("INSERT INTO schedule_item (id,tenant_id,source_id,programme_id,item_date,end_date,start_time,end_time,grade,session,venue,label,sub_label,sort_hint,is_active) "
                "VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,?,NULL,?,1)",
                (str(uuid.uuid4()), TENANT, src_id, prog_id, d, ed, label, i*10))
    n += 1
assert n == 40, "inserted %d, expected 40" % n
c.commit()

cnt = cur.execute("SELECT COUNT(*) FROM schedule_item WHERE source_id=? AND is_active=1", (src_id,)).fetchone()[0]
spans = cur.execute("SELECT COUNT(*) FROM schedule_item WHERE source_id=? AND is_active=1 AND end_date IS NOT NULL", (src_id,)).fetchone()[0]
print("VERIFY items active:", cnt, "| spanning:", spans)
c.close()
print("DONE")
