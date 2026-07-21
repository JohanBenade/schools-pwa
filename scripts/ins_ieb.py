import sqlite3, uuid
from datetime import datetime, timezone

DB = "/var/data/schoolops.db"
TENANT = "MARAGON"
KEA = "0f9674b4-2cdf-438b-b960-48bfedd4be61"
now = datetime.now(timezone.utc).isoformat()

PROG_SLUG = "ieb-conferences"
PROG_NAME = "IEB Conferences"
PROG_COLOUR = "#DB2777"
PROG_SORT = 70
SRC_TITLE = "IEB User Group Conferences 2027"
SRC_TERM = "Term 1 2027"
VENUE = "Birchwood Hotel & Conference Centre"
SUBLABEL = "IEB User Group Conference"

data = []
def add(d, subs, st=None, et=None):
    for s in subs: data.append((d, s, st, et))
add("2027-02-05", ["Agricultural Sciences/Agricultural Management Practices","Further Studies English","Further Studies Mathematics","Further Studies Physics","Design","Equine Studies","Hospitality Studies","Information Technology","Mandarin Second Additional Language","Siswati"])
add("2027-02-06", ["Accounting","Afrikaans Home Language","Computer Applications Technology","Consumer Studies","Dance","English Home Language","Engineering Graphics & Design","French Second Additional Language","Geography","Isizulu","Life Orientation","Mathematics","Physical Sciences","Sport and Exercise Science","Sepedi","Visual Arts"])
add("2027-02-20", ["Afrikaans First Additional Language","Business Studies","Dramatic Arts","Economics","English First Additional Language","German Second Additional Language","History","Isixhosa","Life Sciences","Music","Mathematical Literacy","Sesotho","Setswana","Tourism"])
add("2027-02-18", ["Portuguese Second Additional Language"], "15:00", "17:00")
assert len(data) == 41, "expected 41 source items, got %d" % len(data)

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
            (src_id, TENANT, prog_id, SRC_TITLE, SRC_TERM, KEA, now, now, "Hand-entered from IEB Circular 58/2026. Hebrew SAL + Marine Sciences dates TBA."))
print("source inserted:", src_id)

by_date = {}
for d,s,st,et in data: by_date.setdefault(d, []).append((s,st,et))
n = 0
for d in sorted(by_date):
    for i,(s,st,et) in enumerate(sorted(by_date[d], key=lambda x:x[0].lower())):
        cur.execute("INSERT INTO schedule_item (id,tenant_id,source_id,programme_id,item_date,end_date,start_time,end_time,grade,session,venue,label,sub_label,sort_hint,is_active) "
                    "VALUES (?,?,?,?,?,NULL,?,?,NULL,NULL,?,?,?,?,1)",
                    (str(uuid.uuid4()), TENANT, src_id, prog_id, d, st, et, VENUE, s, SUBLABEL, i*10))
        n += 1
assert n == 41, "inserted %d, expected 41" % n
c.commit()

cnt = cur.execute("SELECT COUNT(*) FROM schedule_item WHERE source_id=? AND is_active=1", (src_id,)).fetchone()[0]
print("VERIFY items active:", cnt)
for r in cur.execute("SELECT item_date,COUNT(*) FROM schedule_item WHERE source_id=? AND is_active=1 GROUP BY item_date ORDER BY item_date", (src_id,)):
    print("  ", r[0], r[1])
c.close()
print("DONE")
