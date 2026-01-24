# SchoolOps Magic Links Reference
## Production URL: schoolops.co.za

---

## How Magic Links Work

- URL format: `schoolops.co.za/?u=CODE`
- Stored in: `user_session` table (`magic_code` column)
- Year-long sessions, no password required
- Password gate: `maragon2026`

---

## Leadership

| Code | User | Role | URL |
|------|------|------|-----|
| pierre | Mr Pierre | principal | schoolops.co.za/?u=pierre |
| kea | Ms Kea | deputy | schoolops.co.za/?u=kea |
| marielouise | Ms Marie-Louise | deputy | schoolops.co.za/?u=marielouise |
| janine | Ms Janine | deputy (PA) | schoolops.co.za/?u=janine |

---

## Grade Heads

| Code | User | Role | URL |
|------|------|------|-----|
| rianette | Ms Rianette | Grade 8 Head | schoolops.co.za/?u=rianette |
| rika | Ms Rika | Grade 9 Head | schoolops.co.za/?u=rika |
| athanathi | Ms Athanathi | Grade 10 Head | schoolops.co.za/?u=athanathi |
| victor | Mr Victor | Grade 11 Head | schoolops.co.za/?u=victor |
| bongi | Ms Bongi | Grade 12 Head | schoolops.co.za/?u=bongi |

---

## Coordinators & Admin

| Code | User | Role | URL |
|------|------|------|-----|
| delene | Ms Delene | Activities/Sport | schoolops.co.za/?u=delene |
| sports | Mr Sports | Sport Coordinator | schoolops.co.za/?u=sports |
| junior | Mr Junior | STASY Admin | schoolops.co.za/?u=junior |
| carina | Ms Carina | IT Teacher | schoolops.co.za/?u=carina |
| rebecca | Ms Rebecca | Office | schoolops.co.za/?u=rebecca |
| admin | Admin | System Admin | schoolops.co.za/?u=admin |

---

## Teachers (A-M)

| Code | User | URL |
|------|------|-----|
| alecia | Ms Alecia | schoolops.co.za/?u=alecia |
| anel | Ms Anel | schoolops.co.za/?u=anel |
| anike | Ms Anike | schoolops.co.za/?u=anike |
| beatrix | Ms Beatrix | schoolops.co.za/?u=beatrix |
| caelynne | Ms Caelynne | schoolops.co.za/?u=caelynne |
| carla | Ms Carla | schoolops.co.za/?u=carla |
| caroline | Ms Caroline | schoolops.co.za/?u=caroline |
| chelsea | Ms Chelsea | schoolops.co.za/?u=chelsea |
| claire | Ms Claire | schoolops.co.za/?u=claire |
| daleen | Ms Daleen | schoolops.co.za/?u=daleen |
| dominique | Ms Dominique | schoolops.co.za/?u=dominique |
| eugeni | Ms Eugeni | schoolops.co.za/?u=eugeni |
| jacqueline | Ms Jacqueline | schoolops.co.za/?u=jacqueline |
| jean | Mr Jean | schoolops.co.za/?u=jean |
| krisna | Ms Krisna | schoolops.co.za/?u=krisna |
| mamello | Ms Mamello | schoolops.co.za/?u=mamello |
| mariska | Ms Mariska | schoolops.co.za/?u=mariska |
| matti | Mr Matti | schoolops.co.za/?u=matti |
| muvo | Mr Muvo | schoolops.co.za/?u=muvo |

---

## Teachers (N-Z)

| Code | User | URL |
|------|------|-----|
| nadia | Ms Nadia | schoolops.co.za/?u=nadia |
| nathi | Mr Nathi | schoolops.co.za/?u=nathi |
| nonhlanhla | Ms Nonhlanhla | schoolops.co.za/?u=nonhlanhla |
| ntando | Mr Ntando | schoolops.co.za/?u=ntando |
| robin | Ms Robin | schoolops.co.za/?u=robin |
| rochelle | Ms Rochelle | schoolops.co.za/?u=rochelle |
| rowena | Ms Rowena | schoolops.co.za/?u=rowena |
| sinqobile | Ms Sinqobile | schoolops.co.za/?u=sinqobile |
| smangaliso | Mr Smangaliso | schoolops.co.za/?u=smangaliso |
| teal | Ms Teal | schoolops.co.za/?u=teal |
| thycha | Ms Thycha | schoolops.co.za/?u=thycha |
| tsholofelo | Ms Tsholofelo | schoolops.co.za/?u=tsholofelo |
| tyla | Ms Tyla | schoolops.co.za/?u=tyla |
| wendyann | Ms Wendyann | schoolops.co.za/?u=wendyann |
| zaudi | Ms Zaudi | schoolops.co.za/?u=zaudi |

---

## Database Reference
```sql
-- Query all magic links
SELECT magic_code, display_name, role 
FROM user_session 
ORDER BY role, display_name;

-- Add new magic link
INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
VALUES (
    lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-' || hex(randomblob(2)) || '-' || hex(randomblob(2)) || '-' || hex(randomblob(6))),
    'MARAGON',
    'STAFF_ID_HERE',
    'magic_code_here',
    'Display Name',
    'teacher',
    0
);
```

---

*Last updated: 24 January 2026*
*Total magic links: 49*
*SchoolOps Project | Johan Benade*
