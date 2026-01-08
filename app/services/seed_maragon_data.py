"""
Seed Maragon Reference Data
Creates realistic test data for pilot demonstration.
625 learners (25 per class x 25 classes) with 10 days of historical attendance.
"""

import uuid
from datetime import date, datetime, timedelta
import random
from app.services.db import get_connection


TENANT_ID = "MARAGON"

# South African first names (diverse mix)
FIRST_NAMES_MALE = [
    "Thabo", "Sipho", "Johan", "Pieter", "Liam", "Ethan", "Kagiso", "Tshepo",
    "Jabulani", "Mandla", "Ryan", "Dylan", "Mpho", "Lesego", "Bongani", "Siyabonga",
    "Michael", "David", "Neo", "Thabiso", "Keagan", "Jason", "Tumelo", "Motheo",
    "William", "James", "Brandon", "Lerato", "Karabo", "Aiden", "Joshua", "Daniel",
    "Themba", "Sibusiso", "Connor", "Tyler", "Lwazi", "Andile", "Matthew", "Luke"
]

FIRST_NAMES_FEMALE = [
    "Lerato", "Naledi", "Emma", "Mia", "Palesa", "Keitumetse", "Amogelang",
    "Jessica", "Caitlin", "Thandiwe", "Nomvula", "Zanele", "Olivia", "Sophia",
    "Isabella", "Grace", "Precious", "Lindiwe", "Amy", "Hannah", "Nicole", "Refilwe",
    "Tshegofatso", "Katlego", "Sarah", "Emily", "Boitumelo", "Nthabi", "Zoe", "Madison",
    "Dineo", "Kgomotso", "Ava", "Lily", "Nomzamo", "Busisiwe", "Rachel", "Abigail"
]

SURNAMES = [
    "van der Merwe", "Nkosi", "Smith", "Molefe", "du Plessis", "Mokoena", "Williams",
    "Botha", "Dlamini", "Pretorius", "Mthembu", "Coetzee", "Sithole", "Joubert",
    "Mahlangu", "Nel", "Khumalo", "Venter", "Ndlovu", "Meyer", "Mashaba", "le Roux",
    "Zulu", "Steyn", "Zwane", "Visser", "Radebe", "Swanepoel", "Ngcobo", "Fourie",
    "Mhlongo", "van Wyk", "Mabena", "du Toit", "Chauke", "Jacobs", "Mokgosi", "Jansen",
    "Motaung", "Swart", "Sibiya", "Kruger", "Maluleke", "Olivier", "Tau", "Erasmus"
]

# Staff from Interhouse document (real names)
STAFF_DATA = [
    # Management
    {"title": "Mr", "first_name": "Pierre", "surname": "Unknown", "display_name": "Mr Pierre", "staff_type": "Management"},
    {"title": "Mrs", "first_name": "Delene", "surname": "Unknown", "display_name": "Mrs Delene", "staff_type": "HOD"},
    
    # Teachers from Officials list
    {"title": "Mrs", "first_name": "Nonhlanhla", "surname": "Unknown", "display_name": "Mrs Nonhlanhla", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Muvo", "surname": "Unknown", "display_name": "Mr Muvo", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Carla", "surname": "Unknown", "display_name": "Mrs Carla", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Shilo", "surname": "Unknown", "display_name": "Mrs Shilo", "staff_type": "Coach"},
    {"title": "Mr", "first_name": "Gavin", "surname": "Unknown", "display_name": "Mr Gavin", "staff_type": "Coach"},
    {"title": "Mr", "first_name": "AJ", "surname": "Unknown", "display_name": "Mr AJ", "staff_type": "Coach"},
    {"title": "Mrs", "first_name": "Zaudi", "surname": "Unknown", "display_name": "Mrs Zaudi", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Anike", "surname": "Unknown", "display_name": "Mrs Anike", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Nadia", "surname": "Stoltz", "display_name": "Mrs Stoltz", "staff_type": "HOD"},
    {"title": "Mrs", "first_name": "Rochelle", "surname": "Unknown", "display_name": "Mrs Rochelle", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Krisna", "surname": "Unknown", "display_name": "Mrs Krisna", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Alecia", "surname": "Unknown", "display_name": "Mrs Alecia", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Matti", "surname": "Unknown", "display_name": "Mr Matti", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Nathi", "surname": "Unknown", "display_name": "Mr Nathi", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Anel", "surname": "Unknown", "display_name": "Mrs Anel", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Jacqueline", "surname": "Unknown", "display_name": "Mrs Jacqueline", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Victor", "surname": "Unknown", "display_name": "Mr Victor", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Carina", "surname": "Unknown", "display_name": "Mrs Carina", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Caroline", "surname": "Unknown", "display_name": "Mrs Caroline", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Bongi", "surname": "Unknown", "display_name": "Mrs Bongi", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Teal", "surname": "Unknown", "display_name": "Mrs Teal", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Eugenie", "surname": "Unknown", "display_name": "Mrs Eugenie", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Christo", "surname": "Unknown", "display_name": "Mr Christo", "staff_type": "Coach"},
    {"title": "Mrs", "first_name": "Mamello", "surname": "Unknown", "display_name": "Mrs Mamello", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Ditokelo", "surname": "Unknown", "display_name": "Mr Ditokelo", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Gift", "surname": "Unknown", "display_name": "Mr Gift", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Rowena", "surname": "Unknown", "display_name": "Mrs Rowena", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Beatrix", "surname": "Unknown", "display_name": "Mrs Beatrix", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Godfrey", "surname": "Unknown", "display_name": "Mr Godfrey", "staff_type": "Coach"},
    {"title": "Mrs", "first_name": "Shirene", "surname": "Unknown", "display_name": "Mrs Shirene", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Chelsea", "surname": "Unknown", "display_name": "Mrs Chelsea", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Dart", "surname": "Unknown", "display_name": "Mr Dart", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Evan", "surname": "Unknown", "display_name": "Mr Evan", "staff_type": "Coach"},
    {"title": "Mr", "first_name": "Ntando", "surname": "Unknown", "display_name": "Mr Ntando", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Athenathi", "surname": "Unknown", "display_name": "Mrs Athenathi", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Thycha", "surname": "Unknown", "display_name": "Mrs Thycha", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Dominique", "surname": "Unknown", "display_name": "Mrs Dominique", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Sinqobile", "surname": "Unknown", "display_name": "Mrs Sinqobile", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Caelynne", "surname": "Unknown", "display_name": "Mrs Caelynne", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Smangaliso", "surname": "Unknown", "display_name": "Mrs Smangaliso", "staff_type": "Teacher"},
    {"title": "Mrs", "first_name": "Mbali", "surname": "Unknown", "display_name": "Mrs Mbali", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Daleen", "surname": "Unknown", "display_name": "Mrs Daleen", "staff_type": "Admin"},
    {"title": "Mrs", "first_name": "Robin", "surname": "Unknown", "display_name": "Mrs Robin", "staff_type": "Admin"},
    {"title": "Mrs", "first_name": "Mariska", "surname": "Unknown", "display_name": "Mrs Mariska", "staff_type": "Admin"},
    {"title": "Mrs", "first_name": "Rika", "surname": "Unknown", "display_name": "Mrs Rika", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Tyla", "surname": "Unknown", "display_name": "Mrs Tyla", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Claire", "surname": "Unknown", "display_name": "Mrs Claire", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Rianette", "surname": "Unknown", "display_name": "Mrs Rianette", "staff_type": "Teacher"},
    {"title": "Mr", "first_name": "Charles", "surname": "Unknown", "display_name": "Mr Charles", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Marie-Louise", "surname": "Unknown", "display_name": "Mrs Marie-Louise", "staff_type": "Support"},
    {"title": "Mrs", "first_name": "Kea", "surname": "Unknown", "display_name": "Mrs Kea", "staff_type": "Support"},
    {"title": "Mr", "first_name": "Njabulo", "surname": "Unknown", "display_name": "Mr Njabulo", "staff_type": "Teacher"},
]

# Grades 8-12 with 5 mentor groups each = 25 total
GRADES = [
    {"grade_name": "Grade 8", "grade_code": "Gr8", "grade_number": 8},
    {"grade_name": "Grade 9", "grade_code": "Gr9", "grade_number": 9},
    {"grade_name": "Grade 10", "grade_code": "Gr10", "grade_number": 10},
    {"grade_name": "Grade 11", "grade_code": "Gr11", "grade_number": 11},
    {"grade_name": "Grade 12", "grade_code": "Gr12", "grade_number": 12},
]

# Mentor group suffixes - 5 per grade
MENTOR_SUFFIXES = ["A", "B", "C", "D", "E"]


def generate_id():
    """Generate UUID for new records."""
    return str(uuid.uuid4())


def seed_grades(cursor):
    """Seed grade data."""
    grade_ids = {}
    for i, grade in enumerate(GRADES):
        grade_id = generate_id()
        cursor.execute("""
            INSERT INTO grade (id, tenant_id, grade_name, grade_code, grade_number, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (grade_id, TENANT_ID, grade["grade_name"], grade["grade_code"], 
              grade["grade_number"], i + 1))
        grade_ids[grade["grade_number"]] = grade_id
    return grade_ids


def seed_staff(cursor):
    """Seed staff data."""
    staff_ids = []
    teacher_ids = []
    
    for staff in STAFF_DATA:
        staff_id = generate_id()
        is_teacher = staff["staff_type"] in ("Teacher", "HOD", "Coach")
        
        cursor.execute("""
            INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, 
                             email, staff_type, can_substitute, can_do_duty, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (staff_id, TENANT_ID, staff["title"], staff["first_name"], staff["surname"],
              staff["display_name"], None, staff["staff_type"],
              1 if is_teacher else 0, 1 if is_teacher else 0))
        
        staff_ids.append(staff_id)
        if is_teacher:
            teacher_ids.append(staff_id)
    
    return staff_ids, teacher_ids


def seed_mentor_groups(cursor, grade_ids, teacher_ids):
    """Seed mentor groups - 5 per grade = 25 total."""
    mentor_group_ids = []
    teacher_index = 0
    
    for grade_num, grade_id in grade_ids.items():
        for suffix in MENTOR_SUFFIXES:
            group_id = generate_id()
            group_name = f"{grade_num}{suffix}"
            
            # Assign mentor (cycle through teachers)
            mentor_id = teacher_ids[teacher_index % len(teacher_ids)]
            teacher_index += 1
            
            cursor.execute("""
                INSERT INTO mentor_group (id, tenant_id, group_name, mentor_id, grade_id)
                VALUES (?, ?, ?, ?, ?)
            """, (group_id, TENANT_ID, group_name, mentor_id, grade_id))
            
            mentor_group_ids.append({
                "id": group_id,
                "name": group_name,
                "grade_id": grade_id,
                "grade_num": grade_num
            })
    
    return mentor_group_ids


def seed_learners(cursor, mentor_groups, grade_ids):
    """Seed learners - 25 per mentor group = 625 total."""
    learner_ids = []
    all_names = FIRST_NAMES_MALE + FIRST_NAMES_FEMALE
    
    for group in mentor_groups:
        for i in range(25):
            learner_id = generate_id()
            first_name = random.choice(all_names)
            surname = random.choice(SURNAMES)
            
            cursor.execute("""
                INSERT INTO learner (id, tenant_id, first_name, surname, grade_id, 
                                   mentor_group_id, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (learner_id, TENANT_ID, first_name, surname, 
                  group["grade_id"], group["id"]))
            
            learner_ids.append({
                "id": learner_id,
                "mentor_group_id": group["id"],
                "grade_num": group["grade_num"]
            })
    
    return learner_ids


def seed_historical_attendance(cursor, mentor_groups, learner_ids):
    """Generate 10 days of historical attendance with realistic patterns."""
    today = date.today()
    
    # Map learners to their mentor groups
    learners_by_group = {}
    for learner in learner_ids:
        gid = learner["mentor_group_id"]
        if gid not in learners_by_group:
            learners_by_group[gid] = []
        learners_by_group[gid].append(learner)
    
    # Select chronic absentees (4 learners with >20% absence rate)
    chronic_absentees = set()
    chronic_candidates = random.sample(learner_ids, min(4, len(learner_ids)))
    for l in chronic_candidates:
        chronic_absentees.add(l["id"])
    
    # Select welfare watchlist (3 learners with consecutive absences)
    welfare_watchlist = set()
    welfare_candidates = [l for l in learner_ids if l["id"] not in chronic_absentees]
    welfare_selected = random.sample(welfare_candidates, min(3, len(welfare_candidates)))
    for l in welfare_selected:
        welfare_watchlist.add(l["id"])
    
    # Generate 10 school days of attendance (skip weekends)
    school_days = []
    check_date = today - timedelta(days=1)
    while len(school_days) < 10:
        if check_date.weekday() < 5:  # Monday=0 to Friday=4
            school_days.append(check_date)
        check_date -= timedelta(days=1)
    
    school_days.reverse()  # Oldest first
    
    for day_index, att_date in enumerate(school_days):
        att_date_str = att_date.isoformat()
        is_monday = att_date.weekday() == 0
        
        for group in mentor_groups:
            # Skip 3 groups on most recent day (for "pending registers" demo)
            if day_index == len(school_days) - 1:  # Most recent day
                if group["name"] in ["9B", "11D", "8A"]:
                    continue
            
            attendance_id = generate_id()
            submitted_time = datetime.combine(att_date, datetime.min.time()) + timedelta(hours=7, minutes=random.randint(30, 55))
            
            cursor.execute("""
                INSERT INTO attendance (id, tenant_id, date, mentor_group_id, 
                                       submitted_at, status)
                VALUES (?, ?, ?, ?, ?, 'Submitted')
            """, (attendance_id, TENANT_ID, att_date_str, group["id"],
                  submitted_time.isoformat()))
            
            group_learners = learners_by_group.get(group["id"], [])
            
            for learner in group_learners:
                # Determine status with realistic patterns
                status = "Present"
                
                # Chronic absentees: 25-35% absent
                if learner["id"] in chronic_absentees:
                    if random.random() < 0.30:
                        status = "Absent"
                
                # Welfare watchlist: absent for last 3-5 days
                elif learner["id"] in welfare_watchlist:
                    # Make them absent for the last 3-5 consecutive days
                    if day_index >= len(school_days) - 4:
                        status = "Absent"
                
                # Grade 9 slightly higher absence (realistic pattern)
                elif group["grade_num"] == 9:
                    if random.random() < 0.08:
                        status = "Absent"
                    elif random.random() < 0.03:
                        status = "Late"
                
                # Monday effect (slightly higher absence)
                elif is_monday:
                    if random.random() < 0.06:
                        status = "Absent"
                    elif random.random() < 0.02:
                        status = "Late"
                
                # Normal days
                else:
                    if random.random() < 0.04:
                        status = "Absent"
                    elif random.random() < 0.015:
                        status = "Late"
                
                entry_id = generate_id()
                cursor.execute("""
                    INSERT INTO attendance_entry (id, attendance_id, learner_id, status)
                    VALUES (?, ?, ?, ?)
                """, (entry_id, attendance_id, learner["id"], status))
    
    # Update tracking table for welfare watchlist
    for learner in learner_ids:
        if learner["id"] in welfare_watchlist:
            consecutive = random.randint(3, 5)
            cursor.execute("""
                INSERT OR REPLACE INTO learner_absent_tracking 
                (learner_id, tenant_id, consecutive_absent_days, last_status, 
                 last_attendance_date, updated_at)
                VALUES (?, ?, ?, 'Absent', ?, ?)
            """, (learner["id"], TENANT_ID, consecutive, 
                  school_days[-1].isoformat(), datetime.now().isoformat()))


def clear_all_data(cursor):
    """Clear all existing data."""
    tables = [
        "attendance_entry",
        "attendance", 
        "learner_absent_tracking",
        "pending_attendance",
        "learner",
        "mentor_group",
        "staff",
        "grade"
    ]
    
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")


def seed_all():
    """Main seed function. Returns counts of seeded data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing data
        clear_all_data(cursor)
        
        # Seed in dependency order
        grade_ids = seed_grades(cursor)
        staff_ids, teacher_ids = seed_staff(cursor)
        mentor_groups = seed_mentor_groups(cursor, grade_ids, teacher_ids)
        learner_ids = seed_learners(cursor, mentor_groups, grade_ids)
        seed_historical_attendance(cursor, mentor_groups, learner_ids)
        
        conn.commit()
        
        # Return counts
        return {
            "staff": len(staff_ids),
            "mentor_groups": len(mentor_groups),
            "learners": len(learner_ids),
            "grades": len(grade_ids)
        }


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeded: {result}")
