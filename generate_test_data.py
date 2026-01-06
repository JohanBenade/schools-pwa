"""
Generate realistic test data for SchoolOps
25 mentor groups x 25 learners = 625 learners
25 staff members (1 per mentor group)
"""

import sqlite3
import uuid
from datetime import datetime

import os
DB_PATH = os.environ.get("DATABASE_PATH", "app/data/schoolops.db")
TENANT_ID = "MARAGON"

# South African first names
FIRST_NAMES_MALE = [
    "Thabo", "Sipho", "Johan", "Pieter", "Michael", "Ryan", "Brandon", "Daniel",
    "Jason", "Tumelo", "Kabelo", "Luyanda", "Neo", "Tshepo", "Kagiso", "Mpho",
    "Blessing", "Gift", "Junior", "Brian", "Kevin", "Ethan", "Joshua", "Matthew",
    "Luke", "Caleb", "Nathan", "Adam", "James", "William", "David", "Thomas",
    "Andile", "Bongani", "Siyabonga", "Themba", "Mandla", "Sibusiso", "Vuyo", "Lwazi"
]

FIRST_NAMES_FEMALE = [
    "Lerato", "Naledi", "Emma", "Sarah", "Megan", "Aisha", "Nomvula", "Zintle",
    "Thandeka", "Chloe", "Palesa", "Jessica", "Amy", "Nicole", "Kayla", "Amber",
    "Courtney", "Jade", "Michaela", "Rebecca", "Hannah", "Rachel", "Grace", "Faith",
    "Hope", "Joy", "Precious", "Princess", "Angel", "Destiny", "Trinity", "Harmony",
    "Lindiwe", "Nompilo", "Ayanda", "Thandi", "Nokuthula", "Zanele", "Nonhlanhla", "Mbali"
]

SURNAMES = [
    "Nkosi", "Dlamini", "Ndlovu", "Zulu", "Khumalo", "Mokoena", "Molefe", "Sithole",
    "Mthembu", "Ngcobo", "Mahlangu", "van der Merwe", "Botha", "Pretorius", "du Plessis",
    "Venter", "Kruger", "Jacobs", "Patel", "Pillay", "Naidoo", "Govender", "Maharaj",
    "Williams", "Johnson", "Smith", "Brown", "Jones", "Davis", "Wilson", "Taylor",
    "Fourie", "Swart", "Coetzee", "Steyn", "van Wyk", "Joubert", "Meyer", "Bosch",
    "le Roux", "Erasmus", "Barnard", "Visser", "Jansen", "Smit", "Nel", "Cilliers"
]

GRADES = [
    {"grade_number": 8, "grade_name": "Grade 8", "grade_code": "Gr8"},
    {"grade_number": 9, "grade_name": "Grade 9", "grade_code": "Gr9"},
    {"grade_number": 10, "grade_name": "Grade 10", "grade_code": "Gr10"},
    {"grade_number": 11, "grade_name": "Grade 11", "grade_code": "Gr11"},
    {"grade_number": 12, "grade_name": "Grade 12", "grade_code": "Gr12"},
]

CLASSES = ["A", "B", "C", "D", "E"]


def generate_id():
    return str(uuid.uuid4())


def clear_data(conn):
    print("Clearing existing data...")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pending_attendance")
    cursor.execute("DELETE FROM attendance_entry")
    cursor.execute("DELETE FROM attendance")
    cursor.execute("DELETE FROM learner_absent_tracking")
    cursor.execute("DELETE FROM learner")
    cursor.execute("DELETE FROM mentor_group")
    cursor.execute("DELETE FROM staff")
    cursor.execute("DELETE FROM grade")
    conn.commit()
    print("  Cleared all tables")


def create_grades(conn):
    print("Creating grades...")
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    grade_ids = {}
    
    for i, g in enumerate(GRADES):
        grade_id = generate_id()
        grade_ids[g["grade_number"]] = grade_id
        cursor.execute('''
            INSERT INTO grade (id, tenant_id, grade_name, grade_code, grade_number, sort_order, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (grade_id, TENANT_ID, g["grade_name"], g["grade_code"], g["grade_number"], i+1, now))
    
    conn.commit()
    print(f"  Created {len(GRADES)} grades")
    return grade_ids


def create_staff(conn):
    print("Creating staff...")
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    import random
    random.seed(123)
    
    staff_list = []
    titles = ["Mr", "Ms", "Mrs", "Dr"]
    
    # Create 40 staff (25 mentors + 15 extra)
    for i in range(40):
        staff_id = generate_id()
        
        if i % 3 == 0:
            title = "Mr"
            first_name = random.choice(FIRST_NAMES_MALE)
        else:
            title = random.choice(["Ms", "Mrs"])
            first_name = random.choice(FIRST_NAMES_FEMALE)
        
        surname = SURNAMES[i % len(SURNAMES)]
        display_name = f"{title} {first_name}"
        
        cursor.execute('''
            INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, email, staff_type, can_substitute, can_do_duty, is_active, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (staff_id, TENANT_ID, title, first_name, surname, display_name, 
              f"{first_name.lower()}.{surname.lower()}@maragon.co.za", "Teacher", 1, 1, 1, now))
        
        staff_list.append({"id": staff_id, "display_name": display_name})
    
    conn.commit()
    print(f"  Created {len(staff_list)} staff members")
    return staff_list


def create_mentor_groups(conn, grade_ids, staff_list):
    print("Creating mentor groups...")
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    group_ids = []
    staff_index = 0
    
    for grade in GRADES:
        grade_num = grade["grade_number"]
        grade_id = grade_ids[grade_num]
        
        for class_letter in CLASSES:
            group_id = generate_id()
            group_name = f"{grade_num}{class_letter}"
            mentor_id = staff_list[staff_index]["id"]
            
            cursor.execute('''
                INSERT INTO mentor_group (id, tenant_id, group_name, mentor_id, grade_id, venue_id, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (group_id, TENANT_ID, group_name, mentor_id, grade_id, None, now))
            
            group_ids.append({"id": group_id, "name": group_name, "grade_id": grade_id})
            staff_index += 1
    
    conn.commit()
    print(f"  Created {len(group_ids)} mentor groups (each with assigned mentor)")
    return group_ids


def create_learners(conn, mentor_groups):
    print("Creating learners...")
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    import random
    random.seed(42)
    
    total = 0
    for group in mentor_groups:
        for i in range(25):
            learner_id = generate_id()
            
            if i % 2 == 0:
                first_name = random.choice(FIRST_NAMES_MALE)
            else:
                first_name = random.choice(FIRST_NAMES_FEMALE)
            
            surname = random.choice(SURNAMES)
            
            cursor.execute('''
                INSERT INTO learner (id, tenant_id, first_name, surname, grade_id, mentor_group_id, house_id, is_active, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (learner_id, TENANT_ID, first_name, surname, group["grade_id"], group["id"], None, 1, now))
            
            total += 1
    
    conn.commit()
    print(f"  Created {total} learners")
    return total


def main():
    print("=" * 50)
    print("GENERATING TEST DATA")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    clear_data(conn)
    grade_ids = create_grades(conn)
    staff_list = create_staff(conn)
    mentor_groups = create_mentor_groups(conn, grade_ids, staff_list)
    learner_count = create_learners(conn, mentor_groups)
    
    conn.close()
    
    print("=" * 50)
    print("TEST DATA COMPLETE")
    print(f"  Grades: {len(grade_ids)}")
    print(f"  Staff: {len(staff_list)}")
    print(f"  Mentor Groups: {len(mentor_groups)}")
    print(f"  Learners: {learner_count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
