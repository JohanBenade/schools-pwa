"""
Seed Sport Duties for Interhouse Athletics 2026
Source: INTERHOUSE_Athletics_OFFICIALS_2026.pdf
"""

import sqlite3
import uuid
from pathlib import Path

def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def generate_id():
    return str(uuid.uuid4())

def get_staff_id_by_name(cursor, first_name, tenant_id="MARAGON"):
    """Look up staff ID by first name."""
    cursor.execute("""
        SELECT id FROM staff 
        WHERE tenant_id = ? AND first_name LIKE ?
        LIMIT 1
    """, (tenant_id, f"%{first_name}%"))
    row = cursor.fetchone()
    return row[0] if row else None

def seed_sport_duties():
    """Seed sport duties for Interhouse Athletics (Jan 16, 2026)."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tenant_id = "MARAGON"
    
    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM sport_duty WHERE tenant_id = ?", (tenant_id,))
    if cursor.fetchone()[0] > 0:
        print("Sport duties already seeded")
        conn.close()
        return {'duties': 0, 'message': 'Already seeded'}
    
    # Find the Interhouse Athletics event (Jan 16)
    cursor.execute("""
        SELECT id FROM sport_event 
        WHERE tenant_id = ? AND event_date = '2026-01-16' AND event_name LIKE '%Athletics%'
    """, (tenant_id,))
    event_row = cursor.fetchone()
    
    if not event_row:
        print("Interhouse Athletics event not found")
        conn.close()
        return {'duties': 0, 'message': 'Event not found'}
    
    event_id = event_row[0]
    print(f"Found event: {event_id}")
    
    # Duty assignments from INTERHOUSE_Athletics_OFFICIALS_2026.pdf
    # Format: (duty_type, duty_role, first_name)
    duties = [
        # Leadership
        ('Leadership', 'Host', 'Pierre'),
        ('Leadership', 'Meeting Director', 'Delene'),
        
        # Announcers
        ('Announcer', 'Announcer', 'Nonhlanhla'),
        ('Announcer', 'Announcer', 'Muvo'),
        ('Announcer', 'Program', 'Carla'),
        
        # Track Officials
        ('Track Judge', 'Track Judge', 'Zaudi'),
        ('Track Judge', 'Track Judge', 'Anike'),
        ('Track Judge', 'Track Judge', 'Nadia'),
        ('Track Judge', 'Track Judge', 'Rochelle'),
        ('Track Judge', 'Track Judge', 'Krisna'),
        ('Track Judge', 'Track Judge', 'Alecia'),
        
        # Timekeepers
        ('Timekeeper', 'Chief Timekeeper', 'Matti'),
        ('Timekeeper', 'Timekeeper', 'Anel'),
        ('Timekeeper', 'Timekeeper', 'Jacqueline'),
        ('Timekeeper', 'Timekeeper', 'Victor'),
        ('Timekeeper', 'Timekeeper', 'Carina'),
        ('Timekeeper', 'Timekeeper', 'Caroline'),
        
        # Scribes
        ('Scribe', 'Scribe', 'Bongi'),
        ('Scribe', 'Scribe', 'Teal'),
        ('Scribe', 'Runner', 'Eugeni'),
        
        # Field Events - High Jump
        ('High Jump', 'High Jump A', 'Mamello'),
        ('High Jump', 'High Jump B', 'Shirene'),
        
        # Field Events - Long Jump
        ('Long Jump', 'Long Jump A', 'Rowena'),
        ('Long Jump', 'Long Jump A', 'Beatrix'),
        
        # Field Events - Discus
        ('Discus', 'Discus A', 'Chelsea'),
        
        # Field Events - Javelin
        ('Javelin', 'Javelin A', 'Ntando'),
        ('Javelin', 'Javelin B', 'Athanathi'),
        ('Javelin', 'Javelin B', 'Thycha'),
        
        # Field Events - Shot Put
        ('Shot Put', 'Shot Put A', 'Dominique'),
        ('Shot Put', 'Shot Put A', 'Sinqobile'),
        ('Shot Put', 'Shot Put B', 'Caelynne'),
        ('Shot Put', 'Shot Put B', 'Smangaliso'),
        
        # Support Roles
        ('Computer', 'Computer', 'Daleen'),
        ('Computer', 'Computer', 'Robin'),
        ('Computer', 'Computer', 'Mariska'),
        
        ('Catering', 'Catering', 'Rika'),
        ('Catering', 'Catering', 'Tyla'),
        ('Catering', 'Catering', 'Claire'),
        
        ('Grade Support', 'Grade 8 Support', 'Rianette'),
        
        ('Gate Duty', 'Gate Duty', 'Marie-Louise'),
        ('Gate Duty', 'Gate Duty', 'Kea'),
    ]
    
    count = 0
    not_found = []
    
    for duty_type, duty_role, first_name in duties:
        staff_id = get_staff_id_by_name(cursor, first_name, tenant_id)
        
        if staff_id:
            cursor.execute("""
                INSERT INTO sport_duty 
                (id, tenant_id, event_id, staff_id, duty_type, duty_role, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Assigned')
            """, (generate_id(), tenant_id, event_id, staff_id, duty_type, duty_role))
            count += 1
        else:
            not_found.append(first_name)
    
    conn.commit()
    conn.close()
    
    if not_found:
        print(f"Staff not found: {set(not_found)}")
    
    print(f"Seeded {count} sport duties for Interhouse Athletics")
    return {'duties': count, 'not_found': list(set(not_found))}


if __name__ == "__main__":
    seed_sport_duties()
