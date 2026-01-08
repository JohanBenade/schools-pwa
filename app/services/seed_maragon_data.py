"""
Seed Maragon staff and mentor group data.
Run via: python -c "from app.services.seed_maragon_data import seed_all; seed_all()"
Or via admin endpoint: /admin/seed-data
"""

from app.services.db import get_connection


def seed_all():
    """Seed all Maragon reference data."""
    print("Starting Maragon data seed...")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing reference data
        print("Clearing existing data...")
        cursor.execute("DELETE FROM pending_attendance")
        cursor.execute("DELETE FROM attendance_entry")
        cursor.execute("DELETE FROM attendance")
        cursor.execute("DELETE FROM learner_absent_tracking")
        cursor.execute("DELETE FROM learner")
        cursor.execute("DELETE FROM mentor_group")
        cursor.execute("DELETE FROM staff")
        cursor.execute("DELETE FROM grade")
        
        # Insert grades
        print("Inserting grades...")
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
        
        # Insert staff
        print("Inserting staff...")
        staff = [
            # MANAGEMENT
            ('staff_001', 'MARAGON', 'Mr', 'Pierre', 'Labuschagne', 'Mr P. Labuschagne', 'Management', 0, 0),
            ('staff_002', 'MARAGON', 'Mrs', 'Marie-Louise', 'Korb', 'Mrs M. Korb', 'Management', 0, 1),
            ('staff_003', 'MARAGON', 'Ms', 'Kea', 'Mogapi', 'Ms K. Mogapi', 'Management', 0, 1),
            # GRADE HEADS
            ('staff_004', 'MARAGON', 'Ms', 'Rianette', 'van Vollenstee', 'Ms R. van Vollenstee', 'Teacher', 1, 1),
            ('staff_005', 'MARAGON', 'Mrs', 'Rika', 'Badenhorst', 'Mrs R. Badenhorst', 'Teacher', 1, 1),
            ('staff_006', 'MARAGON', 'Mr', 'Athanathi', 'Maweni', 'Mr A. Maweni', 'Teacher', 1, 1),
            ('staff_007', 'MARAGON', 'Mr', 'Victor', 'Nyoni', 'Mr V. Nyoni', 'Teacher', 1, 1),
            ('staff_008', 'MARAGON', 'Mrs', 'Bongi', 'Mochabe', 'Mrs B. Mochabe', 'Teacher', 1, 1),
            # SUBJECT HEADS
            ('staff_009', 'MARAGON', 'Mrs', 'Nadia', 'Stoltz', 'Mrs N. Stoltz', 'Teacher', 1, 1),
            ('staff_010', 'MARAGON', 'Ms', 'Anel', 'Meiring', 'Ms A. Meiring', 'Teacher', 1, 1),
            ('staff_011', 'MARAGON', 'Ms', 'Anike', 'Conradie', 'Ms A. Conradie', 'Teacher', 1, 1),
            ('staff_012', 'MARAGON', 'Ms', 'Robin', 'Harle', 'Ms R. Harle', 'Teacher', 1, 1),
            ('staff_013', 'MARAGON', 'Ms', 'Matti', 'van Wyk', 'Ms M. van Wyk', 'Teacher', 1, 1),
            ('staff_014', 'MARAGON', 'Ms', 'Carla', 'van der Walt', 'Ms C. van der Walt', 'Teacher', 1, 1),
            ('staff_015', 'MARAGON', 'Ms', 'Delene', 'Hibbert', 'Ms D. Hibbert', 'Coordinator', 0, 1),
            # GRADE 8 MENTORS
            ('staff_016', 'MARAGON', 'Ms', 'Zaudi', 'Pretorius', 'Ms Z. Pretorius', 'Teacher', 1, 1),
            ('staff_017', 'MARAGON', 'Mr', 'Smangaliso', 'Mdluli', 'Mr S. Mdluli', 'Teacher', 1, 1),
            ('staff_018', 'MARAGON', 'Mr', 'Ntando', 'Mkunjulwa', 'Mr N. Mkunjulwa', 'Teacher', 1, 1),
            ('staff_019', 'MARAGON', 'Ms', 'Nathi', 'Qwelane', 'Ms N. Qwelane', 'Teacher', 1, 1),
            ('staff_020', 'MARAGON', 'Ms', 'Mamello', 'Makgalemele', 'Ms M. Makgalemele', 'Teacher', 1, 1),
            # GRADE 9 MENTORS
            ('staff_021', 'MARAGON', 'Ms', 'Caelynne', 'Prinsloo', 'Ms C. Prinsloo', 'Teacher', 1, 1),
            ('staff_022', 'MARAGON', 'Ms', 'Claire', 'Patrick', 'Ms C. Patrick', 'Teacher', 1, 1),
            ('staff_023', 'MARAGON', 'Ms', 'Eugeni', 'Piek', 'Ms E. Piek', 'Teacher', 1, 1),
            ('staff_024', 'MARAGON', 'Ms', 'Sinqobile', 'Mchunu', 'Ms S. Mchunu', 'Teacher', 1, 1),
            # GRADE 10 MENTORS
            ('staff_025', 'MARAGON', 'Mr', 'Muvo', 'Hlongwana', 'Mr M. Hlongwana', 'Teacher', 1, 1),
            ('staff_026', 'MARAGON', 'Ms', 'Dominique', 'Viljoen', 'Ms D. Viljoen', 'Teacher', 1, 1),
            ('staff_027', 'MARAGON', 'Ms', 'Caroline', 'Shiell', 'Ms C. Shiell', 'Teacher', 1, 1),
            ('staff_028', 'MARAGON', 'Ms', 'Alecia', 'Green', 'Ms A. Green', 'Teacher', 1, 1),
            ('staff_029', 'MARAGON', 'Ms', 'Rochelle', 'Maass', 'Ms R. Maass', 'Teacher', 1, 1),
            # GRADE 11 MENTORS
            ('staff_030', 'MARAGON', 'Ms', 'Tyla', 'Polayya', 'Ms T. Polayya', 'Teacher', 1, 1),
            ('staff_031', 'MARAGON', 'Ms', 'Teal', 'Alves', 'Ms T. Alves', 'Teacher', 1, 1),
            ('staff_032', 'MARAGON', 'Ms', 'Shirene', 'van den Heever', 'Ms S. van den Heever', 'Teacher', 1, 1),
            ('staff_033', 'MARAGON', 'Ms', 'Mariska', 'du Plessis', 'Ms M. du Plessis', 'Teacher', 1, 1),
            ('staff_034', 'MARAGON', 'Ms', 'Thycha', 'Aucamp', 'Ms T. Aucamp', 'Teacher', 1, 1),
            # GRADE 12 MENTORS
            ('staff_035', 'MARAGON', 'Ms', 'Daleen', 'Coetzee', 'Ms D. Coetzee', 'Teacher', 1, 1),
            ('staff_036', 'MARAGON', 'Ms', 'Krisna', 'Els', 'Ms K. Els', 'Teacher', 1, 1),
            ('staff_037', 'MARAGON', 'Ms', 'Jacqueline', 'Sekhula', 'Ms J. Sekhula', 'Teacher', 1, 1),
            ('staff_038', 'MARAGON', 'Ms', 'Beatrix', 'du Toit', 'Ms B. du Toit', 'Teacher', 1, 1),
            ('staff_039', 'MARAGON', 'Ms', 'Tsholofelo', 'Ramphomane', 'Ms T. Ramphomane', 'Teacher', 1, 1),
            # OTHER TEACHERS
            ('staff_040', 'MARAGON', 'Ms', 'Carina', 'Engelbrecht', 'Ms C. Engelbrecht', 'Teacher', 1, 1),
            ('staff_041', 'MARAGON', 'Ms', 'Rowena', 'Kraamwinkel', 'Ms R. Kraamwinkel', 'Teacher', 1, 1),
            ('staff_042', 'MARAGON', 'Ms', 'Nonhlanhla', 'Maswanganyi', 'Ms N. Maswanganyi', 'Teacher', 1, 1),
            ('staff_043', 'MARAGON', 'Ms', 'Chelsea', 'Abrahams', 'Ms C. Abrahams', 'Teacher', 1, 1),
            # TBC PLACEHOLDER
            ('staff_tbc', 'MARAGON', None, 'TBC', 'TBC', 'TBC', 'Teacher', 0, 0),
            # ADMIN & SUPPORT
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
        
        # Insert mentor groups (25 total - Grade Heads supervise but don't have own class)
        print("Inserting mentor groups...")
        mentor_groups = [
            # Grade 8
            ('mg_8_zp', 'MARAGON', '8 ZP', 'staff_016', 'grade_8', 'A007'),
            ('mg_8_sm', 'MARAGON', '8 SM', 'staff_017', 'grade_8', 'A109'),
            ('mg_8_nm', 'MARAGON', '8 NM', 'staff_018', 'grade_8', None),
            ('mg_8_nq', 'MARAGON', '8 NQ', 'staff_019', 'grade_8', 'A102'),
            ('mg_8_mm', 'MARAGON', '8 MM', 'staff_020', 'grade_8', 'A105'),
            # Grade 9
            ('mg_9_cpr', 'MARAGON', '9 CPR', 'staff_021', 'grade_9', 'A003'),
            ('mg_9_cp', 'MARAGON', '9 CP', 'staff_022', 'grade_9', 'A008'),
            ('mg_9_ep', 'MARAGON', '9 EP', 'staff_023', 'grade_9', 'A005'),
            ('mg_9_tbc', 'MARAGON', '9 TBC', 'staff_tbc', 'grade_9', 'B102'),
            ('mg_9_sm', 'MARAGON', '9 SM', 'staff_024', 'grade_9', None),
            # Grade 10
            ('mg_10_mh', 'MARAGON', '10 MH', 'staff_025', 'grade_10', 'C002'),
            ('mg_10_dv', 'MARAGON', '10 DV', 'staff_026', 'grade_10', 'A010'),
            ('mg_10_cs', 'MARAGON', '10 CS', 'staff_027', 'grade_10', 'A121'),
            ('mg_10_ag', 'MARAGON', '10 AG', 'staff_028', 'grade_10', 'D001'),
            ('mg_10_rm', 'MARAGON', '10 RM', 'staff_029', 'grade_10', 'B003'),
            # Grade 11
            ('mg_11_tp', 'MARAGON', '11 TP', 'staff_030', 'grade_11', 'B101'),
            ('mg_11_tm', 'MARAGON', '11 TM', 'staff_031', 'grade_11', 'A103'),
            ('mg_11_svh', 'MARAGON', '11 SVH', 'staff_032', 'grade_11', 'A006'),
            ('mg_11_md', 'MARAGON', '11 MD', 'staff_033', 'grade_11', 'A119'),
            ('mg_11_tau', 'MARAGON', '11 TAU', 'staff_034', 'grade_11', 'A004'),
            # Grade 12
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
        
        # Insert test learners (5 per group = 125 total)
        print("Inserting test learners...")
        
        # South African first names and surnames for realistic test data
        first_names = [
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
            'Keletsong', 'Gosiame', 'Refiloe', 'Modiredi', 'Kgolagano', 'Setshaba',
            'Orateng', 'Thatoyaone', 'Ntsako', 'Ofentseng', 'Molebogeng', 'Remofilwe',
            'Keoagile', 'Thulaganyo', 'Tshwaragano', 'Olerato', 'Kealeboga', 'Leruo',
            'Gontse', 'Olebile', 'Segomotso', 'Tshepang', 'Moagisi', 'Tiro', 'Lefika',
            'Kegomoditswe', 'Poloko', 'Gomolemo', 'Tshimologo', 'Bofelo', 'Dimakatso',
            'Molebatsi', 'Mogau',
        ]
        
        surnames = [
            'Molefe', 'Nkosi', 'Dlamini', 'Mokoena', 'Mahlangu', 'Khumalo', 'Mabaso',
            'Sithole', 'Ndaba', 'Zwane', 'Maseko', 'Ngcobo', 'Radebe', 'Mthembu', 'Zulu',
            'Cele', 'Shabangu', 'Moloi', 'Phiri', 'Motaung', 'Tshabalala', 'Baloyi',
            'Mkhize', 'Sibiya', 'Moyo', 'Buthelezi', 'Nxumalo', 'Mhlongo', 'Chauke',
            'Gumede', 'Khoza', 'Majola', 'Ndlovu', 'Mnguni', 'Hlongwane', 'Mokwena',
            'Vilakazi', 'Mahomed', 'Pillay', 'Govender', 'Naicker', 'Naidoo', 'Singh',
            'Botha', 'van der Merwe', 'Pretorius', 'Jacobs', 'Williams', 'Olivier', 'Nel',
            'Venter', 'Coetzee', 'Steyn', 'Fourie', 'Meyer', 'Marais', 'Joubert',
            'Swanepoel', 'Kruger', 'Smit', 'Lombard', 'Jordaan', 'Prinsloo', 'Barnard',
            'Grobler', 'Pienaar', 'Rossouw', 'Cloete', 'Malan', 'Potgieter', 'Badenhorst',
            'Hendriks', 'Adams', 'Peterson', 'Fredericks', 'Isaacs', 'Davids', 'Erasmus',
            'Muller', 'Visser', 'Bezuidenhout', 'Jansen', 'van Zyl', 'du Toit', 'Steenkamp',
            'Louw', 'Brits', 'Vermaak', 'Schoeman', 'Naude', 'Viljoen', 'Odendaal',
            'van Rensburg', 'Wolmarans', 'Crafford', 'Engelbrecht', 'Dreyer', 'Terblanche',
            'Bester', 'Cronje', 'Snyman', 'Ferreira', 'de Villiers', 'van Wyk', 'Hugo',
            'Booysen', 'Pieterse', 'Groenewald', 'Rautenbach', 'van Heerden', 'Mostert',
            'Lourens', 'Kirsten', 'Strauss', 'Opperman', 'Blignaut', 'Wessels', 'Jonker',
            'Koen', 'Vorster', 'Maritz', 'Bosch', 'Lubbe', 'Strydom', 'Brink', 'Bothma',
            'van Niekerk', 'Swart', 'de Beer', 'Vermeulen', 'Basson',
        ]
        
        learner_id = 1
        for mg_id, mg_name in [(mg[0], mg[2]) for mg in mentor_groups]:
            grade_id = mg_id.split('_')[1]  # Extract grade from mg_8_zp -> 8
            for i in range(5):
                cursor.execute("""
                    INSERT INTO learner (id, tenant_id, first_name, surname, grade_id, mentor_group_id, is_active, synced_at)
                    VALUES (?, 'MARAGON', ?, ?, ?, ?, 1, datetime('now'))
                """, (
                    f'learner_{learner_id:03d}',
                    first_names[(learner_id - 1) % len(first_names)],
                    surnames[(learner_id - 1) % len(surnames)],
                    f'grade_{grade_id}',
                    mg_id
                ))
                learner_id += 1
        
        conn.commit()
        
        # Verify counts
        cursor.execute("SELECT COUNT(*) FROM staff")
        staff_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM mentor_group")
        mg_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM learner")
        learner_count = cursor.fetchone()[0]
        
        print(f"\n=== SEED COMPLETE ===")
        print(f"Staff: {staff_count}")
        print(f"Mentor Groups: {mg_count}")
        print(f"Learners: {learner_count}")
        
        return {
            'staff': staff_count,
            'mentor_groups': mg_count,
            'learners': learner_count
        }


if __name__ == '__main__':
    seed_all()
