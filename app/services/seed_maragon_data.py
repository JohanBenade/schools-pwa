"""
Seed Maragon Reference Data
Creates accurate data based on Teacher's Guide 2026 and Org Chart.
25 mentor groups (5 per grade) with correct teacher assignments.
"""

import uuid
from datetime import date, datetime, timedelta
import random
from app.services.db import get_connection


TENANT_ID = "MARAGON"

# =============================================================================
# STAFF DATA - From Teacher's Guide 2026 + Org Chart
# =============================================================================

STAFF_DATA = [
    # MANAGEMENT
    {"title": "Mr", "first_name": "Pierre", "surname": "Labuschagne", "staff_type": "Management", "role": "Principal"},
    {"title": "Ms", "first_name": "Marie-Louise", "surname": "Korb", "staff_type": "Management", "role": "Deputy Principal (Discipline & Operations)"},
    {"title": "Ms", "first_name": "Kea", "surname": "Mogapi", "staff_type": "Management", "role": "Deputy Principal (Academics)"},
    {"title": "Ms", "first_name": "Delene", "surname": "Hibbert", "staff_type": "Management", "role": "Extra-Mural Co-Ordinator"},
    {"title": "Ms", "first_name": "Anel", "surname": "Meiring", "staff_type": "HOD", "role": "HOD Mathematics"},
    
    # GRADE HEADS (not mentor teachers)
    {"title": "Ms", "first_name": "Rianette", "surname": "van Vollenstee", "staff_type": "Teacher", "role": "Grade 8 Head", "is_grade_head": True, "grade_head_for": 8},
    {"title": "Ms", "first_name": "Rika", "surname": "Badenhorst", "staff_type": "Teacher", "role": "Grade 9 Head", "is_grade_head": True, "grade_head_for": 9},
    {"title": "Ms", "first_name": "Athanathi", "surname": "Maweni", "staff_type": "Teacher", "role": "Grade 10 Head", "is_grade_head": True, "grade_head_for": 10},
    {"title": "Mr", "first_name": "Victor", "surname": "Nyoni", "staff_type": "Teacher", "role": "Grade 11 Head", "is_grade_head": True, "grade_head_for": 11},
    {"title": "Ms", "first_name": "Bongi", "surname": "Mochabe", "staff_type": "Teacher", "role": "Grade 12 Head", "is_grade_head": True, "grade_head_for": 12},
    
    # SUBJECT HEADS
    {"title": "Ms", "first_name": "Nadia", "surname": "Stoltz", "staff_type": "Teacher", "role": "Subject Head: English"},
    {"title": "Ms", "first_name": "Anike", "surname": "Conradie", "staff_type": "Teacher", "role": "Subject Head: Afrikaans"},
    {"title": "Ms", "first_name": "Robin", "surname": "Harle", "staff_type": "Teacher", "role": "Subject Head: Life Orientation"},
    {"title": "Mr", "first_name": "Matti", "surname": "van Wyk", "staff_type": "Teacher", "role": "Subject Head: Physical Sciences"},
    {"title": "Ms", "first_name": "Carla", "surname": "van der Walt", "staff_type": "Teacher", "role": "Subject Head: Multi Subjects"},
    
    # MENTOR TEACHERS - Grade 8 (ZP, SM, NM, NQ, MM)
    {"title": "Ms", "first_name": "Zaudi", "surname": "Pretorius", "staff_type": "Teacher", "mentor_code": "ZP", "mentor_grade": 8},
    {"title": "Mr", "first_name": "Smangaliso", "surname": "Mdluli", "staff_type": "Teacher", "mentor_code": "SM", "mentor_grade": 8},
    {"title": "Mr", "first_name": "Ntando", "surname": "Mkunjulwa", "staff_type": "Teacher", "mentor_code": "NM", "mentor_grade": 8},
    {"title": "Mr", "first_name": "Nathi", "surname": "Qwelane", "staff_type": "Teacher", "mentor_code": "NQ", "mentor_grade": 8},
    {"title": "Ms", "first_name": "Mamello", "surname": "Makgalemele", "staff_type": "Teacher", "mentor_code": "MM", "mentor_grade": 8},
    
    # MENTOR TEACHERS - Grade 9 (CPR, CP, EP, TBC, SM)
    {"title": "Ms", "first_name": "Caelynne", "surname": "Prinsloo", "staff_type": "Teacher", "mentor_code": "CPR", "mentor_grade": 9},
    {"title": "Ms", "first_name": "Claire", "surname": "Patrick", "staff_type": "Teacher", "mentor_code": "CP", "mentor_grade": 9},
    {"title": "Ms", "first_name": "Eugeni", "surname": "Piek", "staff_type": "Teacher", "mentor_code": "EP", "mentor_grade": 9},
    # TBC placeholder - will be added when confirmed
    {"title": "Ms", "first_name": "Sinqobile", "surname": "Mchunu", "staff_type": "Teacher", "mentor_code": "SM", "mentor_grade": 9},
    
    # MENTOR TEACHERS - Grade 10 (MH, DV, CS, AG, RM)
    {"title": "Mr", "first_name": "Muvo", "surname": "Hlongwana", "staff_type": "Teacher", "mentor_code": "MH", "mentor_grade": 10},
    {"title": "Ms", "first_name": "Dominique", "surname": "Viljoen", "staff_type": "Teacher", "mentor_code": "DV", "mentor_grade": 10},
    {"title": "Ms", "first_name": "Caroline", "surname": "Shiell", "staff_type": "Teacher", "mentor_code": "CS", "mentor_grade": 10},
    {"title": "Ms", "first_name": "Alecia", "surname": "Green", "staff_type": "Teacher", "mentor_code": "AG", "mentor_grade": 10},
    {"title": "Ms", "first_name": "Rochelle", "surname": "Maass", "staff_type": "Teacher", "mentor_code": "RM", "mentor_grade": 10},
    
    # MENTOR TEACHERS - Grade 11 (TP, TM, SVH, MD, TAU)
    {"title": "Ms", "first_name": "Tyla", "surname": "Polayya", "staff_type": "Teacher", "mentor_code": "TP", "mentor_grade": 11},
    {"title": "Ms", "first_name": "Teal", "surname": "Mittendorf", "staff_type": "Teacher", "mentor_code": "TM", "mentor_grade": 11},
    {"title": "Ms", "first_name": "Shirene", "surname": "van den Heever", "staff_type": "Teacher", "mentor_code": "SVH", "mentor_grade": 11},
    {"title": "Ms", "first_name": "Mariska", "surname": "du Plessis", "staff_type": "Teacher", "mentor_code": "MD", "mentor_grade": 11},
    {"title": "Ms", "first_name": "Thycha", "surname": "Aucamp", "staff_type": "Teacher", "mentor_code": "TAU", "mentor_grade": 11},
    
    # MENTOR TEACHERS - Grade 12 (DC, KE, JS, BD, TR)
    {"title": "Ms", "first_name": "Daleen", "surname": "Coetzee", "staff_type": "Teacher", "mentor_code": "DC", "mentor_grade": 12},
    {"title": "Ms", "first_name": "Krisna", "surname": "Els", "staff_type": "Teacher", "mentor_code": "KE", "mentor_grade": 12},
    {"title": "Ms", "first_name": "Jacqueline", "surname": "Sekhula", "staff_type": "Teacher", "mentor_code": "JS", "mentor_grade": 12},
    {"title": "Ms", "first_name": "Beatrix", "surname": "du Toit", "staff_type": "Teacher", "mentor_code": "BD", "mentor_grade": 12},
    {"title": "Ms", "first_name": "Tsholofelo", "surname": "Ramphomane", "staff_type": "Teacher", "mentor_code": "TR", "mentor_grade": 12},
    
    # OTHER TEACHERS (not mentors)
    {"title": "Ms", "first_name": "Carina", "surname": "Engelbrecht", "staff_type": "Teacher"},
    {"title": "Ms", "first_name": "Rowena", "surname": "Kraamwinkel", "staff_type": "Teacher"},
    {"title": "Ms", "first_name": "Nonhlanhla", "surname": "Maswanganyi", "staff_type": "Teacher"},
    {"title": "Ms", "first_name": "Chelsea", "surname": "Abrahams", "staff_type": "Teacher"},
    
    # ADMIN STAFF
    {"title": "Ms", "first_name": "Rebecca", "surname": "Munyai", "staff_type": "Admin", "role": "Receptionist"},
    {"title": "Ms", "first_name": "Annette", "surname": "Croeser", "staff_type": "Admin", "role": "Bursar"},
    {"title": "Ms", "first_name": "Janine", "surname": "Willemse", "staff_type": "Admin", "role": "HR / PA"},
    {"title": "Mr", "first_name": "Junior", "surname": "Letsoalo", "staff_type": "Admin", "role": "STASY Admin"},
    {"title": "Mr", "first_name": "Njabulo", "surname": "Ndimande", "staff_type": "Support", "role": "IT Support"},
    {"title": "Ms", "first_name": "Tamika", "surname": "Hibbard", "staff_type": "Support", "role": "Educational Psychologist"},
    {"title": "Ms", "first_name": "Andiswa", "surname": "Tsewana", "staff_type": "Support", "role": "Lab Assistant"},
]

# Grades 8-12
GRADES = [
    {"grade_name": "Grade 8", "grade_code": "Gr8", "grade_number": 8},
    {"grade_name": "Grade 9", "grade_code": "Gr9", "grade_number": 9},
    {"grade_name": "Grade 10", "grade_code": "Gr10", "grade_number": 10},
    {"grade_name": "Grade 11", "grade_code": "Gr11", "grade_number": 11},
    {"grade_name": "Grade 12", "grade_code": "Gr12", "grade_number": 12},
]

# 25 Mentor Groups - 5 per grade with correct codes
MENTOR_GROUPS = [
    # Grade 8
    {"grade": 8, "code": "ZP"},
    {"grade": 8, "code": "SM"},
    {"grade": 8, "code": "NM"},
    {"grade": 8, "code": "NQ"},
    {"grade": 8, "code": "MM"},
    # Grade 9
    {"grade": 9, "code": "CPR"},
    {"grade": 9, "code": "CP"},
    {"grade": 9, "code": "EP"},
    {"grade": 9, "code": "TBC"},
    {"grade": 9, "code": "SM"},
    # Grade 10
    {"grade": 10, "code": "MH"},
    {"grade": 10, "code": "DV"},
    {"grade": 10, "code": "CS"},
    {"grade": 10, "code": "AG"},
    {"grade": 10, "code": "RM"},
    # Grade 11
    {"grade": 11, "code": "TP"},
    {"grade": 11, "code": "TM"},
    {"grade": 11, "code": "SVH"},
    {"grade": 11, "code": "MD"},
    {"grade": 11, "code": "TAU"},
    # Grade 12
    {"grade": 12, "code": "DC"},
    {"grade": 12, "code": "KE"},
    {"grade": 12, "code": "JS"},
    {"grade": 12, "code": "BD"},
    {"grade": 12, "code": "TR"},
]

# South African first names for test learners
FIRST_NAMES_MALE = [
    "Thabo", "Sipho", "Johan", "Pieter", "Liam", "Ethan", "Kagiso", "Tshepo",
    "Jabulani", "Mandla", "Ryan", "Dylan", "Mpho", "Lesego", "Bongani", "Siyabonga",
    "Michael", "David", "Neo", "Thabiso", "Keagan", "Jason", "Tumelo", "Motheo",
    "William", "James", "Brandon", "Karabo", "Aiden", "Joshua", "Daniel", "Matthew"
]

FIRST_NAMES_FEMALE = [
    "Lerato", "Naledi", "Emma", "Mia", "Palesa", "Keitumetse", "Amogelang",
    "Jessica", "Caitlin", "Thandiwe", "Nomvula", "Zanele", "Olivia", "Sophia",
    "Isabella", "Grace", "Precious", "Lindiwe", "Amy", "Hannah", "Nicole", "Refilwe",
    "Tshegofatso", "Katlego", "Sarah", "Emily", "Boitumelo", "Zoe", "Madison", "Ava"
]

SURNAMES = [
    "van der Merwe", "Nkosi", "Smith", "Molefe", "du Plessis", "Mokoena", "Williams",
    "Botha", "Dlamini", "Pretorius", "Mthembu", "Coetzee", "Sithole", "Joubert",
    "Mahlangu", "Nel", "Khumalo", "Venter", "Ndlovu", "Meyer", "Mashaba", "le Roux",
    "Zulu", "Steyn", "Zwane", "Visser", "Radebe", "Swanepoel", "Ngcobo", "Fourie"
]


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
    """Seed staff data with proper flags."""
    staff_by_code = {}  # mentor_code -> staff_id
    
    for staff in STAFF_DATA:
        staff_id = generate_id()
        
        # Build display name: "Ms Nadia" or "Mr Pierre"
        display_name = f"{staff['title']} {staff['first_name']}"
        
        # Determine flags
        is_teacher = staff["staff_type"] in ("Teacher", "HOD", "Management")
        is_mentor = "mentor_code" in staff
        is_grade_head = staff.get("is_grade_head", False)
        can_substitute = is_teacher and not is_grade_head  # Grade heads don't substitute
        
        cursor.execute("""
            INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, 
                             email, staff_type, can_substitute, can_do_duty, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (staff_id, TENANT_ID, staff["title"], staff["first_name"], staff["surname"],
              display_name, None, staff["staff_type"],
              1 if can_substitute else 0, 1 if is_teacher else 0))
        
        # Track mentor teachers by code for group assignment
        if is_mentor:
            code_key = f"{staff['mentor_grade']}_{staff['mentor_code']}"
            staff_by_code[code_key] = staff_id
    
    return staff_by_code


def seed_mentor_groups(cursor, grade_ids, staff_by_code):
    """Seed mentor groups with correct codes and teacher assignments."""
    mentor_group_data = []
    
    for mg in MENTOR_GROUPS:
        group_id = generate_id()
        grade_num = mg["grade"]
        code = mg["code"]
        group_name = f"{grade_num} {code}"  # e.g., "8 ZP", "9 CPR"
        
        grade_id = grade_ids[grade_num]
        
        # Find mentor teacher
        code_key = f"{grade_num}_{code}"
        mentor_id = staff_by_code.get(code_key)  # None for TBC
        
        cursor.execute("""
            INSERT INTO mentor_group (id, tenant_id, group_name, mentor_id, grade_id)
            VALUES (?, ?, ?, ?, ?)
        """, (group_id, TENANT_ID, group_name, mentor_id, grade_id))
        
        mentor_group_data.append({
            "id": group_id,
            "name": group_name,
            "grade_id": grade_id,
            "grade_num": grade_num
        })
    
    return mentor_group_data


def seed_learners(cursor, mentor_groups, grade_ids):
    """Seed test learners - 25 per mentor group = 625 total."""
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
            if day_index == len(school_days) - 1:
                if group["name"] in ["9 TBC", "11 MD", "8 NM"]:
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
                status = "Present"
                
                # Chronic absentees: 25-35% absent
                if learner["id"] in chronic_absentees:
                    if random.random() < 0.30:
                        status = "Absent"
                
                # Welfare watchlist: absent for last 3-5 days
                elif learner["id"] in welfare_watchlist:
                    if day_index >= len(school_days) - 4:
                        status = "Absent"
                
                # Grade 9 slightly higher absence
                elif group["grade_num"] == 9:
                    if random.random() < 0.08:
                        status = "Absent"
                    elif random.random() < 0.03:
                        status = "Late"
                
                # Monday effect
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
        staff_by_code = seed_staff(cursor)
        mentor_groups = seed_mentor_groups(cursor, grade_ids, staff_by_code)
        learner_ids = seed_learners(cursor, mentor_groups, grade_ids)
        seed_historical_attendance(cursor, mentor_groups, learner_ids)
        
        conn.commit()
        
        # Return counts
        return {
            "staff": len(STAFF_DATA),
            "mentor_groups": len(mentor_groups),
            "learners": len(learner_ids),
            "grades": len(grade_ids)
        }


if __name__ == "__main__":
    result = seed_all()
    print(f"Seeded: {result}")
