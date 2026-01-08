"""
Seed Maragon staff, learners, and attendance history.
Generates realistic demo data for Principal Dashboard.

Run via: python -c "from app.services.seed_maragon_data import seed_all; seed_all()"
Or via admin endpoint: /admin/seed-data
"""

import random
from datetime import date, datetime, timedelta
from app.services.db import get_connection


# South African names for realistic test data
FIRST_NAMES = [
    'Thabo', 'Lerato', 'Sipho', 'Naledi', 'Kagiso', 'Mpho', 'Tshegofatso', 'Lebo',
    'Keitumetse', 'Bokang', 'Palesa', 'Tebogo', 'Kgomotso', 'Neo', 'Dineo',
    'Kamogelo', 'Boitumelo', 'Lesedi', 'Refilwe', 'Tumelo', 'Amogelang', 'Motheo',
    'Omphile', 'Rethabile', 'Karabo', 'Oratile', 'Tshiamo', 'Katlego', 'Bontle',
    'Ofentse', 'Tshepiso', 'Goitseone', 'Phenyo', 'Realeboga', 'Masego',
    'Letlotlo', 'Rorisang', 'Kutlwano', 'Lethabo', 'Mohau', 'Tlotlo', 'Onkarabile',
    'Bohlale', 'Itumeleng', 'Thato', 'Kopano', 'Boipelo', 'Keketso', 'Refentse',
    'Warona', 'Lorato', 'Kabelo', 'Malebogo', 'Setlhabi', 'Koketso', 'Mosidi',
    'Tshepo', 'Mmathabo', 'Bokamoso', 'Kelebogile', 'Gopolang', 'Reitumetse',
    'Moagi', 'Paballo', 'Olebogeng', 'Tumisang', 'Kefilwe', 'Oratilwe', 'Lefentse',
    'Khumo', 'Motlalepule', 'Thapelo', 'Nthabiseng', 'Boingotlo', 'Goitsemang',
    'Keneilwe', 'Ratanang', 'Resego', 'Lebogang', 'Katleho', 'Omphe', 'Relebohile',
    'Mogomotsi', 'Omolemo', 'Tshwanelo', 'Motswedi', 'Botshelo', 'Lesego',
    'Reabetswe', 'Kgothatso', 'Tlhompho', 'Seipati', 'Mothusi', 'Otlotleng',
]

SURNAMES = [
    'Molefe', 'Nkosi', 'Dlamini', 'Mokoena', 'Mahlangu', 'Khumalo', 'Mabaso',
    'Sithole', 'Ndaba', 'Zwane', 'Maseko', 'Ngcobo', 'Radebe', 'Mthembu', 'Zulu',
    'Cele', 'Shabangu', 'Moloi', 'Phiri', 'Motaung', 'Tshabalala', 'Baloyi',
    'Mkhize', 'Sibiya', 'Moyo', 'Buthelezi', 'Nxumalo', 'Mhlongo', 'Chauke',
    'Gumede', 'Khoza', 'Majola', 'Ndlovu', 'Mnguni', 'Hlongwane', 'Mokwena',
    'Vilakazi', 'Mahomed', 'Pillay', 'Govender', 'Naicker', 'Naidoo', 'Singh',
    'Botha', 'van der Merwe', 'Pretorius', 'Jacobs', 'Williams', 'Olivier', 'Nel',
    'Venter', 'Coetzee', 'Steyn', 'Fourie', 'Meyer', 'Marais', 'Joubert',
]


def seed_all():
    """Seed all Maragon reference data with attendance history."""
    print("=" * 60)
    print("SEEDING MARAGON DATA")
    print("=" * 60)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing data
        print("\n[1/6] Clearing existing data...")
        for table in ['pending_attendance', 'attendance_entry', 'attendance', 
                      'learner_absent_tracking', 'learner', 'mentor_group', 'staff', 'grade']:
            cursor.execute(f"DELETE FROM {table}")
        
        # Insert grades
        print("[2/6] Inserting grades...")
        grades = [
            ('grade_8', 'MARAGON', 'Grade 8', 'Gr8', 8, 1),
            ('grade_9', 'MARAGON', 'Grade 9', 'Gr9', 9, 2),
            ('grade_10', 'MARAGON', 'Grade 10', 'Gr10', 10, 3),
            ('grade_11', 'MARAGON', 'Grade 11', 'Gr11', 11, 4),
            ('grade_12', 'MARAGON', 'Grade 12', 'Gr12', 12, 5),
        ]
        cursor.executemany("""
            INSERT INTO grade (id, tenant_id, grade_name, grade_code, grade_number, sort_order, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, grades)
        
        # Insert staff (abbreviated - same as before)
        print("[3/6] Inserting 54 staff members...")
        staff = [
            ('staff_001', 'MARAGON', 'Mr', 'Pierre', 'Labuschagne', 'Mr P. Labuschagne', 'Management', 0, 0),
            ('staff_002', 'MARAGON', 'Mrs', 'Marie-Louise', 'Korb', 'Mrs M. Korb', 'Management', 0, 1),
            ('staff_003', 'MARAGON', 'Ms', 'Kea', 'Mogapi', 'Ms K. Mogapi', 'Management', 0, 1),
            ('staff_004', 'MARAGON', 'Ms', 'Rianette', 'van Vollenstee', 'Ms R. van Vollenstee', 'Teacher', 1, 1),
            ('staff_005', 'MARAGON', 'Mrs', 'Rika', 'Badenhorst', 'Mrs R. Badenhorst', 'Teacher', 1, 1),
            ('staff_006', 'MARAGON', 'Mr', 'Athanathi', 'Maweni', 'Mr A. Maweni', 'Teacher', 1, 1),
            ('staff_007', 'MARAGON', 'Mr', 'Victor', 'Nyoni', 'Mr V. Nyoni', 'Teacher', 1, 1),
            ('staff_008', 'MARAGON', 'Mrs', 'Bongi', 'Mochabe', 'Mrs B. Mochabe', 'Teacher', 1, 1),
            ('staff_009', 'MARAGON', 'Mrs', 'Nadia', 'Stoltz', 'Mrs N. Stoltz', 'Teacher', 1, 1),
            ('staff_010', 'MARAGON', 'Ms', 'Anel', 'Meiring', 'Ms A. Meiring', 'Teacher', 1, 1),
            ('staff_011', 'MARAGON', 'Ms', 'Anike', 'Conradie', 'Ms A. Conradie', 'Teacher', 1, 1),
            ('staff_012', 'MARAGON', 'Ms', 'Robin', 'Harle', 'Ms R. Harle', 'Teacher', 1, 1),
            ('staff_013', 'MARAGON', 'Ms', 'Matti', 'van Wyk', 'Ms M. van Wyk', 'Teacher', 1, 1),
            ('staff_014', 'MARAGON', 'Ms', 'Carla', 'van der Walt', 'Ms C. van der Walt', 'Teacher', 1, 1),
            ('staff_015', 'MARAGON', 'Ms', 'Delene', 'Hibbert', 'Ms D. Hibbert', 'Coordinator', 0, 1),
            ('staff_016', 'MARAGON', 'Ms', 'Zaudi', 'Pretorius', 'Ms Z. Pretorius', 'Teacher', 1, 1),
            ('staff_017', 'MARAGON', 'Mr', 'Smangaliso', 'Mdluli', 'Mr S. Mdluli', 'Teacher', 1, 1),
            ('staff_018', 'MARAGON', 'Mr', 'Ntando', 'Mkunjulwa', 'Mr N. Mkunjulwa', 'Teacher', 1, 1),
            ('staff_019', 'MARAGON', 'Ms', 'Nathi', 'Qwelane', 'Ms N. Qwelane', 'Teacher', 1, 1),
            ('staff_020', 'MARAGON', 'Ms', 'Mamello', 'Makgalemele', 'Ms M. Makgalemele', 'Teacher', 1, 1),
            ('staff_021', 'MARAGON', 'Ms', 'Caelynne', 'Prinsloo', 'Ms C. Prinsloo', 'Teacher', 1, 1),
            ('staff_022', 'MARAGON', 'Ms', 'Claire', 'Patrick', 'Ms C. Patrick', 'Teacher', 1, 1),
            ('staff_023', 'MARAGON', 'Ms', 'Eugeni', 'Piek', 'Ms E. Piek', 'Teacher', 1, 1),
            ('staff_024', 'MARAGON', 'Ms', 'Sinqobile', 'Mchunu', 'Ms S. Mchunu', 'Teacher', 1, 1),
            ('staff_025', 'MARAGON', 'Mr', 'Muvo', 'Hlongwana', 'Mr M. Hlongwana', 'Teacher', 1, 1),
            ('staff_026', 'MARAGON', 'Ms', 'Dominique', 'Viljoen', 'Ms D. Viljoen', 'Teacher', 1, 1),
            ('staff_027', 'MARAGON', 'Ms', 'Caroline', 'Shiell', 'Ms C. Shiell', 'Teacher', 1, 1),
            ('staff_028', 'MARAGON', 'Ms', 'Alecia', 'Green', 'Ms A. Green', 'Teacher', 1, 1),
            ('staff_029', 'MARAGON', 'Ms', 'Rochelle', 'Maass', 'Ms R. Maass', 'Teacher', 1, 1),
            ('staff_030', 'MARAGON', 'Ms', 'Tyla', 'Polayya', 'Ms T. Polayya', 'Teacher', 1, 1),
            ('staff_031', 'MARAGON', 'Ms', 'Teal', 'Alves', 'Ms T. Alves', 'Teacher', 1, 1),
            ('staff_032', 'MARAGON', 'Ms', 'Shirene', 'van den Heever', 'Ms S. van den Heever', 'Teacher', 1, 1),
            ('staff_033', 'MARAGON', 'Ms', 'Mariska', 'du Plessis', 'Ms M. du Plessis', 'Teacher', 1, 1),
            ('staff_034', 'MARAGON', 'Ms', 'Thycha', 'Aucamp', 'Ms T. Aucamp', 'Teacher', 1, 1),
            ('staff_035', 'MARAGON', 'Ms', 'Daleen', 'Coetzee', 'Ms D. Coetzee', 'Teacher', 1, 1),
            ('staff_036', 'MARAGON', 'Ms', 'Krisna', 'Els', 'Ms K. Els', 'Teacher', 1, 1),
            ('staff_037', 'MARAGON', 'Ms', 'Jacqueline', 'Sekhula', 'Ms J. Sekhula', 'Teacher', 1, 1),
            ('staff_038', 'MARAGON', 'Ms', 'Beatrix', 'du Toit', 'Ms B. du Toit', 'Teacher', 1, 1),
            ('staff_039', 'MARAGON', 'Ms', 'Tsholofelo', 'Ramphomane', 'Ms T. Ramphomane', 'Teacher', 1, 1),
            ('staff_040', 'MARAGON', 'Ms', 'Carina', 'Engelbrecht', 'Ms C. Engelbrecht', 'Teacher', 1, 1),
            ('staff_041', 'MARAGON', 'Ms', 'Rowena', 'Kraamwinkel', 'Ms R. Kraamwinkel', 'Teacher', 1, 1),
            ('staff_042', 'MARAGON', 'Ms', 'Nonhlanhla', 'Maswanganyi', 'Ms N. Maswanganyi', 'Teacher', 1, 1),
            ('staff_043', 'MARAGON', 'Ms', 'Chelsea', 'Abrahams', 'Ms C. Abrahams', 'Teacher', 1, 1),
            ('staff_tbc', 'MARAGON', None, 'TBC', 'TBC', 'TBC', 'Teacher', 0, 0),
            ('staff_044', 'MARAGON', 'Ms', 'Rebecca', 'Munyai', 'Ms R. Munyai', 'Admin', 0, 0),
            ('staff_045', 'MARAGON', 'Ms', 'Annette', 'Croeser', 'Ms A. Croeser', 'Admin', 0, 0),
            ('staff_046', 'MARAGON', 'Ms', 'Janine', 'Willemse', 'Ms J. Willemse', 'Admin', 0, 0),
            ('staff_047', 'MARAGON', 'Mr', 'Junior', 'Letsoalo', 'Mr J. Letsoalo', 'Admin', 0, 0),
            ('staff_048', 'MARAGON', 'Mr', 'Njabulo', 'Ndimande', 'Mr N. Ndimande', 'IT', 0, 0),
            ('staff_049', 'MARAGON', 'Ms', 'Tamika', 'Hibbard', 'Ms T. Hibbard', 'Psychologist', 0, 0),
            ('staff_050', 'MARAGON', 'Ms', 'Andiswa', 'Tsewana', 'Ms A. Tsewana', 'LabAssistant', 0, 0),
            ('staff_051', 'MARAGON', 'Mr', 'Johnson', 'Makamu', 'Mr J. Makamu', 'Support', 0, 0),
            ('staff_052', 'MARAGON', 'Mr', 'Gift', 'Tladi', 'Mr G. Tladi', 'Support', 0, 0),
            ('staff_053', 'MARAGON', 'Mr', 'Kabelo', 'Motubatse', 'Mr K. Motubatse', 'Support', 0, 0),
        ]
        cursor.executemany("""
            INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, staff_type, can_substitute, can_do_duty, is_active, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
        """, staff)
        
        # Insert mentor groups
        print("[4/6] Inserting 25 mentor groups...")
        mentor_groups = [
            ('mg_8_zp', 'MARAGON', '8 ZP', 'staff_016', 'grade_8', 'A007'),
            ('mg_8_sm', 'MARAGON', '8 SM', 'staff_017', 'grade_8', 'A109'),
            ('mg_8_nm', 'MARAGON', '8 NM', 'staff_018', 'grade_8', None),
            ('mg_8_nq', 'MARAGON', '8 NQ', 'staff_019', 'grade_8', 'A102'),
            ('mg_8_mm', 'MARAGON', '8 MM', 'staff_020', 'grade_8', 'A105'),
            ('mg_9_cpr', 'MARAGON', '9 CPR', 'staff_021', 'grade_9', 'A003'),
            ('mg_9_cp', 'MARAGON', '9 CP', 'staff_022', 'grade_9', 'A008'),
            ('mg_9_ep', 'MARAGON', '9 EP', 'staff_023', 'grade_9', 'A005'),
            ('mg_9_tbc', 'MARAGON', '9 TBC', 'staff_tbc', 'grade_9', 'B102'),
            ('mg_9_sm', 'MARAGON', '9 SM', 'staff_024', 'grade_9', None),
            ('mg_10_mh', 'MARAGON', '10 MH', 'staff_025', 'grade_10', 'C002'),
            ('mg_10_dv', 'MARAGON', '10 DV', 'staff_026', 'grade_10', 'A010'),
            ('mg_10_cs', 'MARAGON', '10 CS', 'staff_027', 'grade_10', 'A121'),
            ('mg_10_ag', 'MARAGON', '10 AG', 'staff_028', 'grade_10', 'D001'),
            ('mg_10_rm', 'MARAGON', '10 RM', 'staff_029', 'grade_10', 'B003'),
            ('mg_11_tp', 'MARAGON', '11 TP', 'staff_030', 'grade_11', 'B101'),
            ('mg_11_tm', 'MARAGON', '11 TM', 'staff_031', 'grade_11', 'A103'),
            ('mg_11_svh', 'MARAGON', '11 SVH', 'staff_032', 'grade_11', 'A006'),
            ('mg_11_md', 'MARAGON', '11 MD', 'staff_033', 'grade_11', 'A119'),
            ('mg_11_tau', 'MARAGON', '11 TAU', 'staff_034', 'grade_11', 'A004'),
            ('mg_12_dc', 'MARAGON', '12 DC', 'staff_035', 'grade_12', 'A113'),
            ('mg_12_ke', 'MARAGON', '12 KE', 'staff_036', 'grade_12', 'A106'),
            ('mg_12_js', 'MARAGON', '12 JS', 'staff_037', 'grade_12', 'B002'),
            ('mg_12_bd', 'MARAGON', '12 BD', 'staff_038', 'grade_12', 'B001'),
            ('mg_12_tr', 'MARAGON', '12 TR', 'staff_039', 'grade_12', 'A111'),
        ]
        cursor.executemany("""
            INSERT INTO mentor_group (id, tenant_id, group_name, mentor_id, grade_id, venue_id, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """, mentor_groups)
        
        # Insert learners (25 per class = 625 total)
        print("[5/6] Inserting 625 learners (25 per class)...")
        
        random.seed(42)
        learner_id = 1
        learner_ids_by_group = {}
        
        for mg_id, _, group_name, _, grade_id, _ in mentor_groups:
            learner_ids_by_group[mg_id] = []
            
            for i in range(25):
                lid = f'learner_{learner_id:03d}'
                fname = random.choice(FIRST_NAMES)
                sname = random.choice(SURNAMES)
                
                cursor.execute("""
                    INSERT INTO learner (id, tenant_id, first_name, surname, grade_id, mentor_group_id, is_active, synced_at)
                    VALUES (?, 'MARAGON', ?, ?, ?, ?, 1, datetime('now'))
                """, (lid, fname, sname, grade_id, mg_id))
                
                learner_ids_by_group[mg_id].append(lid)
                learner_id += 1
        
        # Generate 10 days of attendance history
        print("[6/6] Generating 10 days of attendance history...")
        
        today = date.today()
        
        # Find last 10 weekdays
        school_days = []
        check_date = today
        while len(school_days) < 10:
            if check_date.weekday() < 5:
                school_days.append(check_date)
            check_date -= timedelta(days=1)
        school_days.reverse()
        
        # Welfare watchlist learners (consecutive absences)
        welfare_watchlist = {
            'learner_012': 5,  # 5 consecutive days
            'learner_078': 4,  # 4 consecutive days  
            'learner_134': 3,  # 3 consecutive days
        }
        
        # Chronic absentees (~35% absence rate)
        chronic_absentees = ['learner_047', 'learner_089', 'learner_156', 'learner_201']
        
        attendance_id = 1
        entry_id = 1
        
        for day_idx, school_date in enumerate(school_days):
            date_str = school_date.isoformat()
            is_monday = school_date.weekday() == 0
            is_today = school_date == today
            days_from_end = len(school_days) - day_idx - 1
            
            for mg_id, _, group_name, mentor_id, grade_id, _ in mentor_groups:
                # Skip some registers for today (demo pending)
                if is_today and mg_id in ['mg_9_tbc', 'mg_11_md', 'mg_8_nm']:
                    continue
                
                att_id = f'att_{attendance_id:04d}'
                
                if is_today:
                    submit_hour = random.randint(7, 8)
                    submit_min = random.randint(30, 59) if submit_hour == 7 else random.randint(0, 15)
                    submitted_at = f"{date_str}T{submit_hour:02d}:{submit_min:02d}:00"
                else:
                    submitted_at = f"{date_str}T07:{random.randint(35, 55):02d}:00"
                
                cursor.execute("""
                    INSERT INTO attendance (id, tenant_id, mentor_group_id, date, submitted_at, submitted_by)
                    VALUES (?, 'MARAGON', ?, ?, ?, ?)
                """, (att_id, mg_id, date_str, submitted_at, mentor_id))
                
                for lid in learner_ids_by_group[mg_id]:
                    ent_id = f'entry_{entry_id:05d}'
                    status = 'Present'
                    
                    # Welfare watchlist - consecutive absences at end
                    if lid in welfare_watchlist and days_from_end < welfare_watchlist[lid]:
                        status = 'Absent'
                    # Chronic absentees
                    elif lid in chronic_absentees and random.random() < 0.35:
                        status = 'Absent'
                    # Grade 9 slightly worse
                    elif grade_id == 'grade_9' and random.random() < 0.07:
                        status = 'Absent'
                    # Mondays worse
                    elif is_monday and random.random() < 0.05:
                        status = 'Absent'
                    # General absence
                    elif random.random() < 0.025:
                        status = 'Absent'
                    # Late arrivals
                    elif random.random() < 0.012:
                        status = 'Late'
                    
                    cursor.execute("""
                        INSERT INTO attendance_entry (id, attendance_id, learner_id, status, stasy_captured)
                        VALUES (?, ?, ?, ?, ?)
                    """, (ent_id, att_id, lid, status, 1 if not is_today else 0))
                    
                    entry_id += 1
                
                attendance_id += 1
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM staff")
        staff_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mentor_group")
        mg_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM learner")
        learner_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM attendance")
        att_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM attendance_entry")
        entry_count = cursor.fetchone()[0]
        
        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"Staff:              {staff_count}")
        print(f"Mentor Groups:      {mg_count}")
        print(f"Learners:           {learner_count}")
        print(f"Attendance Records: {att_count}")
        print(f"Attendance Entries: {entry_count}")
        print("=" * 60)
        
        return {
            'staff': staff_count,
            'mentor_groups': mg_count,
            'learners': learner_count,
            'attendance_records': att_count,
            'attendance_entries': entry_count
        }


if __name__ == '__main__':
    seed_all()
