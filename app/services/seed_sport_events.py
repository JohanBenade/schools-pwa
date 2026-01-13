"""
Seed Sport Events for Term 1 2026
Source: Staff_duty_list_sport_Term_1_2026.pdf
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

def seed_sport_events():
    """Seed Term 1 2026 sport events."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    tenant_id = "MARAGON"
    
    cursor.execute("SELECT COUNT(*) FROM sport_event WHERE tenant_id = ?", (tenant_id,))
    if cursor.fetchone()[0] > 0:
        print("Sport events already seeded")
        conn.close()
        return {'events': 0, 'message': 'Already seeded'}
    
    print("Seeding Term 1 2026 sport events...")
    
    events = [
        ('2026-01-15', '08:00', '10:00', 'Interhouse Quiz', 'Quiz', 'Home', 'Auditorium', 1),
        ('2026-01-15', '10:30', '15:00', 'Interhouse Swimming', 'Swimming', 'Home', 'Swimming Pool', 1),
        ('2026-01-16', '08:00', '16:00', 'Interhouse Athletics', 'Athletics', 'Home', 'Athletics Track', 1),
        ('2026-01-22', '13:00', '17:00', 'Swimming Gala', 'Swimming', 'Away', '@ Sutherland', 0),
        ('2026-01-24', '06:30', '16:00', 'Athletics Meeting', 'Athletics', 'Away', '@ Eduplex', 0),
        ('2026-01-29', '14:00', '17:00', 'Swimming Gala', 'Swimming', 'Home', 'Swimming Pool', 0),
        ('2026-01-30', '14:30', '19:00', 'Athletics Meeting', 'Athletics', 'Away', '@ Southdowns', 0),
        ('2026-02-05', '13:00', '18:00', 'Swimming Gala', 'Swimming', 'Away', '@ Sutherland', 0),
        ('2026-02-06', '13:30', '19:00', 'Athletics Meeting', 'Athletics', 'Home', 'Athletics Track', 0),
        ('2026-02-12', '14:00', '18:00', 'Swimming Gala', 'Swimming', 'Home', 'Swimming Pool', 0),
        ('2026-02-13', '13:30', '18:00', 'Athletics Meeting', 'Athletics', 'Away', '@ Reddford', 0),
        ('2026-02-16', '06:00', '18:00', 'Super Inter High', 'Multi-Sport', 'Away', 'TBC', 0),
        ('2026-02-18', '13:00', '18:00', 'Swimming Inter High', 'Swimming', 'Away', 'TBC', 0),
        ('2026-02-23', '06:00', '18:00', 'Athletics Inter High', 'Athletics', 'Away', 'TBC', 0),
        ('2026-03-05', '14:30', '17:30', 'Netball vs HS Dirk Postma', 'Netball', 'Home', 'Netball Courts', 0),
        ('2026-03-06', '14:30', '17:30', 'Rugby vs FH Odendaal', 'Rugby', 'Home', 'Rugby Field', 0),
        ('2026-03-13', '14:30', '17:30', 'Netball Fixture', 'Netball', 'Away', 'TBC', 0),
        ('2026-03-14', '08:00', '16:00', 'Athletics Super League', 'Athletics', 'Away', 'TBC', 0),
        ('2026-03-18', '14:30', '17:30', 'Rugby vs Curro Roodeplaat', 'Rugby', 'Home', 'Rugby Field', 0),
        ('2026-03-20', '14:30', '17:30', 'Netball Fixture', 'Netball', 'Home', 'Netball Courts', 0),
        ('2026-03-21', '08:00', '16:00', 'Swimming Gala', 'Swimming', 'Away', 'TBC', 0),
        ('2026-03-25', '13:00', '18:00', 'Rugby vs Willowridge', 'Rugby', 'Away', '@ Willowridge', 0),
    ]
    
    count = 0
    for event_date, start, end, name, sport, loc_type, venue, affects in events:
        cursor.execute("""
            INSERT INTO sport_event 
            (id, tenant_id, event_date, start_time, end_time, event_name, sport_type, 
             location_type, venue_name, affects_timetable, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Scheduled')
        """, (generate_id(), tenant_id, event_date, start, end, name, sport, loc_type, venue, affects))
        count += 1
    
    conn.commit()
    conn.close()
    
    print(f"Seeded {count} sport events for Term 1 2026")
    return {'events': count}


if __name__ == "__main__":
    seed_sport_events()
