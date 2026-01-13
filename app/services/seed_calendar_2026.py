"""
Seed school_calendar with Maragon 2026 academic year data.
Source: Days_Calendar_2026_Final.pdf
"""

import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, date, timedelta

def get_db_path():
    import os
    default_path = Path(__file__).parent.parent / "data" / "schoolops.db"
    return Path(os.environ.get("DATABASE_PATH", default_path))

def generate_id():
    return str(uuid.uuid4())

def seed_calendar():
    """Seed the school calendar for 2026."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tenant_id = "MARAGON"
    
    # Check if already seeded
    cursor.execute("SELECT COUNT(*) FROM school_calendar WHERE tenant_id = ?", (tenant_id,))
    if cursor.fetchone()[0] > 0:
        print("Calendar already seeded")
        conn.close()
        return
    
    print("Seeding 2026 school calendar...")
    
    # Public holidays 2026
    public_holidays = {
        date(2026, 1, 1): "New Year's Day",
        date(2026, 3, 21): "Human Rights Day",
        date(2026, 4, 3): "Good Friday",
        date(2026, 4, 6): "Family Day",
        date(2026, 4, 27): "Freedom Day",
        date(2026, 5, 1): "Workers' Day",
        date(2026, 6, 16): "Youth Day",
        date(2026, 8, 9): "Women's Day",
        date(2026, 9, 24): "Heritage Day",
        date(2026, 12, 16): "Day of Reconciliation",
        date(2026, 12, 25): "Christmas Day",
        date(2026, 12, 26): "Day of Goodwill",
    }
    
    # Special school holidays
    special_holidays = {
        date(2026, 6, 15): "Special school holiday",
        date(2026, 8, 10): "Special school holiday",
    }
    
    # Term dates (inclusive)
    terms = [
        (1, date(2026, 1, 14), date(2026, 3, 27)),
        (2, date(2026, 4, 13), date(2026, 6, 26)),
        (3, date(2026, 7, 21), date(2026, 9, 23)),
        (4, date(2026, 10, 12), date(2026, 12, 4)),
    ]
    
    # Teachers only days (before term starts)
    teachers_only = {
        date(2026, 1, 12),
        date(2026, 1, 13),
    }
    
    # Special event days (no normal timetable)
    event_days = {
        date(2026, 1, 14): "Orientation",
        date(2026, 1, 15): "Interhouse Swimming",
        date(2026, 1, 16): "Interhouse Athletics",
    }
    
    # Cycle day mapping from the PDF
    # Term 1: First cycle day is 19 Jan (D1)
    # The cycle continues D1-D7 repeating, skipping weekends and holidays
    
    cycle_day_map = {}
    
    # Term 1 cycle days (from PDF)
    t1_cycle = [
        (date(2026, 1, 19), 1), (date(2026, 1, 20), 2), (date(2026, 1, 21), 3),
        (date(2026, 1, 22), 4), (date(2026, 1, 23), 5),
        (date(2026, 1, 26), 6), (date(2026, 1, 27), 7), (date(2026, 1, 28), 1),
        (date(2026, 1, 29), 2), (date(2026, 1, 30), 3),
        (date(2026, 2, 2), 4), (date(2026, 2, 3), 5), (date(2026, 2, 4), 6),
        (date(2026, 2, 5), 7), (date(2026, 2, 6), 1),
        (date(2026, 2, 9), 2), (date(2026, 2, 10), 3), (date(2026, 2, 11), 4),
        (date(2026, 2, 12), 5), (date(2026, 2, 13), 6),
        (date(2026, 2, 16), 7), (date(2026, 2, 17), 1), (date(2026, 2, 18), 2),
        (date(2026, 2, 19), 3), (date(2026, 2, 20), 4),
        (date(2026, 2, 23), 5), (date(2026, 2, 24), 6), (date(2026, 2, 25), 7),
        (date(2026, 2, 26), 1), (date(2026, 2, 27), 2),
        (date(2026, 3, 2), 3), (date(2026, 3, 3), 4), (date(2026, 3, 4), 5),
        (date(2026, 3, 5), 6), (date(2026, 3, 6), 7),
        (date(2026, 3, 9), 1), (date(2026, 3, 10), 2), (date(2026, 3, 11), 3),
        (date(2026, 3, 12), 4), (date(2026, 3, 13), 5),
        (date(2026, 3, 16), 6), (date(2026, 3, 17), 7), (date(2026, 3, 18), 1),
        (date(2026, 3, 19), 2), (date(2026, 3, 20), 3),
        # 21 March = Human Rights Day (public holiday)
        (date(2026, 3, 23), 4), (date(2026, 3, 24), 5), (date(2026, 3, 25), 6),
        (date(2026, 3, 26), 7), (date(2026, 3, 27), 1),
    ]
    for d, c in t1_cycle:
        cycle_day_map[d] = c
    
    # Term 2 cycle days (from PDF - starts D2 on 13 April)
    t2_cycle = [
        (date(2026, 4, 13), 2), (date(2026, 4, 14), 3), (date(2026, 4, 15), 4),
        (date(2026, 4, 16), 5), (date(2026, 4, 17), 6),
        (date(2026, 4, 20), 7), (date(2026, 4, 21), 1), (date(2026, 4, 22), 2),
        (date(2026, 4, 23), 3), (date(2026, 4, 24), 4),
        # 27 April = Freedom Day
        (date(2026, 4, 28), 5), (date(2026, 4, 29), 6), (date(2026, 4, 30), 7),
        # 1 May = Workers Day, skip D1
        (date(2026, 5, 4), 2), (date(2026, 5, 5), 3), (date(2026, 5, 6), 4),
        (date(2026, 5, 7), 5), (date(2026, 5, 8), 6),
        (date(2026, 5, 11), 7), (date(2026, 5, 12), 1), (date(2026, 5, 13), 2),
        (date(2026, 5, 14), 3), (date(2026, 5, 15), 4),
        (date(2026, 5, 18), 5), (date(2026, 5, 19), 6), (date(2026, 5, 20), 7),
        (date(2026, 5, 21), 1), (date(2026, 5, 22), 2),
        (date(2026, 5, 25), 3), (date(2026, 5, 26), 4), (date(2026, 5, 27), 5),
        (date(2026, 5, 28), 5), (date(2026, 5, 29), 6),
        # June exams start - cycle days may vary
        (date(2026, 6, 1), 7), (date(2026, 6, 2), 1), (date(2026, 6, 3), 2),
        (date(2026, 6, 4), 3), (date(2026, 6, 5), 4),
        (date(2026, 6, 8), 5), (date(2026, 6, 9), 6), (date(2026, 6, 10), 7),
        (date(2026, 6, 11), 1), (date(2026, 6, 12), 2),
        # 15 June special holiday, 16 June Youth Day
        (date(2026, 6, 17), 3), (date(2026, 6, 18), 4), (date(2026, 6, 19), 5),
        (date(2026, 6, 22), 6), (date(2026, 6, 23), 7), (date(2026, 6, 24), 1),
        (date(2026, 6, 25), 2), (date(2026, 6, 26), 3),
    ]
    for d, c in t2_cycle:
        cycle_day_map[d] = c
    
    # Term 3 cycle days (from PDF - starts D1 on 21 July)
    t3_cycle = [
        (date(2026, 7, 21), 6), (date(2026, 7, 22), 7), (date(2026, 7, 23), 1),
        (date(2026, 7, 24), 2),
        (date(2026, 7, 27), 3), (date(2026, 7, 28), 4), (date(2026, 7, 29), 5),
        (date(2026, 7, 30), 6), (date(2026, 7, 31), 7),
        (date(2026, 8, 3), 1), (date(2026, 8, 4), 2), (date(2026, 8, 5), 3),
        (date(2026, 8, 6), 4), (date(2026, 8, 7), 5),
        # 9 Aug Women's Day, 10 Aug special holiday
        (date(2026, 8, 11), 6), (date(2026, 8, 12), 7), (date(2026, 8, 13), 1),
        (date(2026, 8, 14), 2),
        (date(2026, 8, 17), 3), (date(2026, 8, 18), 4), (date(2026, 8, 19), 5),
        (date(2026, 8, 20), 6), (date(2026, 8, 21), 7),
        (date(2026, 8, 24), 1), (date(2026, 8, 25), 2), (date(2026, 8, 26), 3),
        (date(2026, 8, 27), 4), (date(2026, 8, 28), 5),
        (date(2026, 8, 31), 6),
        (date(2026, 9, 1), 7), (date(2026, 9, 2), 1), (date(2026, 9, 3), 2),
        (date(2026, 9, 4), 3),
        (date(2026, 9, 7), 4), (date(2026, 9, 8), 5), (date(2026, 9, 9), 6),
        (date(2026, 9, 10), 7), (date(2026, 9, 11), 1),
        (date(2026, 9, 14), 2), (date(2026, 9, 15), 3), (date(2026, 9, 16), 4),
        (date(2026, 9, 17), 5), (date(2026, 9, 18), 6),
        (date(2026, 9, 21), 7), (date(2026, 9, 22), 1), (date(2026, 9, 23), 2),
    ]
    for d, c in t3_cycle:
        cycle_day_map[d] = c
    
    # Term 4 cycle days (from PDF - starts D7 on 12 Oct)
    t4_cycle = [
        (date(2026, 10, 12), 3), (date(2026, 10, 13), 4), (date(2026, 10, 14), 5),
        (date(2026, 10, 15), 6), (date(2026, 10, 16), 7),
        (date(2026, 10, 19), 1), (date(2026, 10, 20), 2), (date(2026, 10, 21), 3),
        (date(2026, 10, 22), 4), (date(2026, 10, 23), 5),
        (date(2026, 10, 26), 6), (date(2026, 10, 27), 7), (date(2026, 10, 28), 1),
        (date(2026, 10, 29), 2), (date(2026, 10, 30), 3),
        # November - mostly exams
        (date(2026, 11, 2), 4), (date(2026, 11, 3), 5),
        # Rest of Nov/Dec is exam period - no cycle days
    ]
    for d, c in t4_cycle:
        cycle_day_map[d] = c
    
    # Generate all days for 2026
    start = date(2026, 1, 1)
    end = date(2026, 12, 31)
    current = start
    
    count = 0
    while current <= end:
        weekday = current.strftime('%A').lower()
        
        # Determine bell schedule type
        if weekday in ['monday', 'wednesday']:
            bell_schedule = 'type_a'
        elif weekday in ['tuesday', 'thursday']:
            bell_schedule = 'type_b'
        elif weekday == 'friday':
            bell_schedule = 'type_c'
        else:
            bell_schedule = 'none'  # Weekend
        
        # Determine day type and is_school_day
        cycle_day = cycle_day_map.get(current)
        day_name = f"D{cycle_day}" if cycle_day else None
        
        if weekday in ['saturday', 'sunday']:
            day_type = 'weekend'
            is_school_day = 0
        elif current in public_holidays:
            day_type = 'public_holiday'
            day_name = public_holidays[current]
            is_school_day = 0
        elif current in special_holidays:
            day_type = 'holiday'
            day_name = special_holidays[current]
            is_school_day = 0
        elif current in teachers_only:
            day_type = 'teachers_only'
            day_name = 'Teachers Only'
            is_school_day = 1  # Teachers have duty
        elif current in event_days:
            day_type = 'event'
            day_name = event_days[current]
            is_school_day = 1  # Staff required
        elif cycle_day:
            day_type = 'academic'
            is_school_day = 1
        else:
            # Check if in term but no cycle day (could be exam or holiday)
            in_term = False
            term_num = None
            for t, t_start, t_end in terms:
                if t_start <= current <= t_end:
                    in_term = True
                    term_num = t
                    break
            
            if in_term:
                day_type = 'exam'  # In term but no cycle day = exam period
                is_school_day = 1
            else:
                day_type = 'holiday'
                is_school_day = 0
        
        # Determine term
        term = None
        for t, t_start, t_end in terms:
            if t_start <= current <= t_end:
                term = t
                break
        
        cursor.execute("""
            INSERT INTO school_calendar 
            (id, tenant_id, date, cycle_day, day_type, day_name, weekday, bell_schedule, is_school_day, term)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (generate_id(), tenant_id, current.isoformat(), cycle_day, day_type, 
              day_name, weekday, bell_schedule, is_school_day, term))
        
        count += 1
        current += timedelta(days=1)
    
    conn.commit()
    conn.close()
    
    print(f"Seeded {count} calendar days for 2026")


if __name__ == "__main__":
    seed_calendar()
