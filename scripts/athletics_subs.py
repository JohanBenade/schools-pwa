import sqlite3, uuid
from datetime import datetime

conn = sqlite3.connect('/var/data/schoolops.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
T='MARAGON'; D='2026-02-23'; CD=5; NOW=datetime.now().isoformat()
names=['Nadia','Teal','Thycha','Rochelle','Smangaliso','Bongi','Claire','Mariska',
       'Jacqueline','Rika','Nathi','Sinqobile','Rowena','Caelynne','Muvo',
       'Marie-Louise','Kea','Carla','Jean','Mamello','Ntando']

# Resolve staff
staff=[]
for n in names:
    c.execute("SELECT id,display_name,first_name FROM staff WHERE first_name=? AND tenant_id=?",(n,T))
    r=c.fetchone()
    if r: staff.append(dict(r))
    else: print(f"SKIP: {n}")
aids=[s['id'] for s in staff]
print(f"\n{len(staff)} teachers resolved\n")

# Create absences
for s in staff:
    c.execute("SELECT id FROM absence WHERE staff_id=? AND absence_date=? AND tenant_id=? AND status NOT IN ('Resolved','Cancelled')",(s['id'],D,T))
    e=c.fetchone()
    if e:
        s['aid']=e['id']; print(f"EXISTS: {s['display_name']}")
    else:
        a=str(uuid.uuid4())
        c.execute("INSERT INTO absence(id,tenant_id,staff_id,absence_date,end_date,absence_type,reason,status,is_full_day,is_open_ended,reported_at,created_at,updated_at)VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (a,T,s['id'],D,D,'School Event','Interhigh Athletics','Reported',1,0,NOW,NOW,NOW))
        s['aid']=a; print(f"Created: {s['display_name']}")

# Find Gr10/11/12 periods needing cover on D5
nc=[]
for s in staff:
    c.execute("""SELECT t.class_name,t.subject,p.id pid,p.period_number pn,p.period_name pnm,v.venue_code vc
    FROM timetable_slot t JOIN period p ON t.period_id=p.id LEFT JOIN venue v ON t.venue_id=v.id
    WHERE t.staff_id=? AND t.cycle_day=? AND t.class_name NOT LIKE 'Gr8%' AND t.class_name NOT LIKE 'Gr9%'
    ORDER BY p.sort_order""",(s['id'],CD))
    for r in c.fetchall():
        nc.append({'s':s,'pid':r['pid'],'pn':r['pn'],'pnm':r['pnm'],'cn':r['class_name'],'su':r['subject'],'vc':r['vc']})
print(f"\n{len(nc)} periods need cover\n")

# Get available subs
ph=','.join(['?']*len(aids))
c.execute(f"SELECT id,display_name,first_name FROM staff WHERE tenant_id=? AND can_substitute=1 AND is_active=1 AND id NOT IN({ph}) ORDER BY first_name",[T]+aids)
av=[dict(r) for r in c.fetchall()]

# Map each sub's teaching periods on D5
st={}
for sub in av:
    c.execute("SELECT p.period_number FROM timetable_slot t JOIN period p ON t.period_id=p.id WHERE t.staff_id=? AND t.cycle_day=?",(sub['id'],CD))
    st[sub['id']]=set(r['period_number'] for r in c.fetchall())

sl={s['id']:0 for s in av}
sm={s['id']:s for s in av}
asgn=0; pend=0

# Assign subs by free period match, load-balanced
for slot in nc:
    pn=slot['pn']
    cands=[s for s in av if pn not in st.get(s['id'],set())]
    cands.sort(key=lambda s:(sl[s['id']],s['first_name']))
    sid=None; sn=None; status='Pending'
    if cands:
        ch=cands[0]; sid=ch['id']; sn=ch['display_name']
        sl[sid]+=1; st[sid].add(pn); status='Assigned'; asgn+=1
    else:
        pend+=1
    c.execute("INSERT INTO substitute_request(id,tenant_id,absence_id,period_id,substitute_id,request_date,status,is_mentor_duty,class_name,subject,venue_name,created_at,updated_at)VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (str(uuid.uuid4()),T,slot['s']['aid'],slot['pid'],sid,D,status,0,slot['cn'],slot['su'],slot['vc'],NOW,NOW))
    tag=f"-> {sn}" if sn else "-> UNCOVERED"
    print(f"{slot['s']['display_name']:15} P{pn} {slot['cn']:12} {slot['su']:15} {tag}")

# Update absence statuses
for s in staff:
    c.execute("SELECT COUNT(*) t,SUM(CASE WHEN substitute_id IS NOT NULL THEN 1 ELSE 0 END) cv FROM substitute_request WHERE absence_id=? AND request_date=?",(s['aid'],D))
    r=c.fetchone(); tot=r['t'] or 0; cov=r['cv'] or 0
    ns='Covered' if cov==tot and tot>0 else 'Partial' if cov>0 else 'Reported'
    c.execute("UPDATE absence SET status=? WHERE id=?",(ns,s['aid']))

conn.commit(); conn.close()
print(f"\n=== SUMMARY ===\nAssigned: {asgn}\nPending: {pend}\nTotal: {asgn+pend}\n\nSub load:")
for sid,load in sorted(sl.items(),key=lambda x:-x[1]):
    if load>0: print(f"  {sm[sid]['display_name']:18} {load}")
