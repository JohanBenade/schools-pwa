"""
Seed venues and user sessions for Maragon Mooikloof
Based on Maragon_Mooikloof_Structure_v2.pdf
"""

from app.services.db import get_connection, generate_id

TENANT_ID = "MARAGON"


def seed_venues():
    """Seed all Maragon venues."""
    
    venues = [
        # A Block Ground Floor (A001-A012)
        ("A001", "A001 - Ms Anike", "classroom", "A_Ground", 1),
        ("A002", "A002 - Ms Rika", "classroom", "A_Ground", 2),
        ("A003", "A003 - Ms Caelynne", "classroom", "A_Ground", 3),
        ("A004", "A004 - Ms Thycha", "classroom", "A_Ground", 4),
        ("A005", "A005 - Ms Eugeni", "classroom", "A_Ground", 5),
        ("A006", "A006 - Ms Shirene", "classroom", "A_Ground", 6),
        ("A007", "A007 - Ms Zaudi", "classroom", "A_Ground", 7),
        ("A008", "A008 - Ms Claire", "classroom", "A_Ground", 8),
        ("A009", "A009 - Ms Rianette", "classroom", "A_Ground", 9),
        ("A010", "A010 - Ms Dominique", "classroom", "A_Ground", 10),
        ("A011", "A011 - Kitchen", "facility", "A_Ground", 11),
        ("A012", "A012 - Ms Carla", "classroom", "A_Ground", 12),
        
        # A Block First Floor (A101-A112)
        ("A101", "A101 - Mr Victor", "classroom", "A_First", 101),
        ("A102", "A102 - Mr Nathi", "classroom", "A_First", 102),
        ("A103", "A103 - Ms Teal", "classroom", "A_First", 103),
        ("A104", "A104 - Ms Nadia", "classroom", "A_First", 104),
        ("A105", "A105 - Ms Mamello", "classroom", "A_First", 105),
        ("A106", "A106 - Ms Krisna", "classroom", "A_First", 106),
        ("A107", "A107 - Ms Robin", "classroom", "A_First", 107),
        ("A108", "A108 - Ms Bongi", "classroom", "A_First", 108),
        ("A109", "A109 - Mr Smangaliso", "classroom", "A_First", 109),
        ("A110", "A110 - Ms Athanathi", "classroom", "A_First", 110),
        ("A111", "A111 - Ms Tsholofelo", "classroom", "A_First", 111),
        ("A112", "A112 - Ms Anel", "classroom", "A_First", 112),
        
        # A Block Admin/IT Area (A113-A121)
        ("A113", "A113 - Ms Daleen (CAT)", "classroom", "A_Admin", 113),
        ("A114", "A114 - Sport Office", "office", "A_Admin", 114),
        ("A115", "A115 - IT Support", "office", "A_Admin", 115),
        ("A116", "A116 - Student Council", "office", "A_Admin", 116),
        ("A117", "A117 - Ed Psychologist", "office", "A_Admin", 117),
        ("A118", "A118 - Ms Carina (IT)", "classroom", "A_Admin", 118),
        ("A119", "A119 - New CAT", "classroom", "A_Admin", 119),
        ("A120", "A120 - Mr Matti", "classroom", "A_Admin", 120),
        ("A121", "A121 - Ms Caroline", "classroom", "A_Admin", 121),
        
        # B Block
        ("B001", "B001 - Ms Beatrix", "classroom", "B_Block", 201),
        ("B002", "B002 - Ms Jacqueline", "classroom", "B_Block", 202),
        ("B003", "B003 - Ms Rochelle", "classroom", "B_Block", 203),
        ("B101", "B101 - Ms Tyla", "classroom", "B_Block", 211),
        ("B102", "B102 - TBC", "classroom", "B_Block", 212),
        ("B103", "B103 - Ms Nonhlanhla", "classroom", "B_Block", 213),
        
        # C Block
        ("C002", "C002 - Mr Muvo", "classroom", "C_Block", 301),
        
        # D Block
        ("D001", "D001 - Ms Alecia", "classroom", "D_Block", 401),
        ("D002", "D002 - Ms Rowena", "classroom", "D_Block", 402),
        
        # Outdoor / Terrain Areas
        ("QUAD", "Quad", "terrain", "Outdoor", 501),
        ("PEACE", "Peace Park", "terrain", "Outdoor", 502),
        ("ABOVE_PEACE", "Above Peace Park", "terrain", "Outdoor", 503),
        ("PRAISE", "Praise Park", "terrain", "Outdoor", 504),
        ("DOWN_UNDER", "Down Under", "terrain", "Outdoor", 505),
        ("PAVILION", "Pavilion", "terrain", "Outdoor", 506),
        ("BOUNDARIES", "Boundaries", "terrain", "Outdoor", 507),
        ("AUDITORIUM", "Auditorium Area", "terrain", "Outdoor", 508),
        ("STAFFROOM", "Staffroom Area", "terrain", "Outdoor", 509),
        ("SPORTS", "Sports Fields", "terrain", "Outdoor", 510),
        ("PARKING", "Parking Area", "terrain", "Outdoor", 511),
        ("POOL", "Swimming Pool", "facility", "Outdoor", 512),
        
        # Admin Areas
        ("RECEPTION", "Reception", "office", "Admin", 601),
        ("PRINCIPAL", "Principal Office", "office", "Admin", 602),
        ("STAFFROOM_INT", "Staffroom (Inside)", "facility", "Admin", 603),
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing venues
        cursor.execute("DELETE FROM venue WHERE tenant_id = ?", (TENANT_ID,))
        
        # Insert venues
        for venue_code, venue_name, venue_type, block, sort_order in venues:
            venue_id = generate_id()
            cursor.execute("""
                INSERT INTO venue (id, tenant_id, venue_code, venue_name, venue_type, block, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (venue_id, TENANT_ID, venue_code, venue_name, venue_type, block, sort_order))
        
        conn.commit()
        return len(venues)


def seed_staff_venues():
    """Assign staff to their home venues based on Maragon structure."""
    
    # Map: staff surname -> venue_code
    staff_venue_map = {
        "Conradie": "A001",
        "Badenhorst": "A002",
        "Prinsloo": "A003",
        "Aucamp": "A004",
        "Piek": "A005",
        "van den Heever": "A006",
        "Pretorius": "A007",
        "Patrick": "A008",
        "van Vollenstee": "A009",
        "Viljoen": "A010",
        "van der Walt": "A012",
        "Nyoni": "A101",
        "Qwelane": "A102",
        "Mittendorf": "A103",
        "Stoltz": "A104",
        "Makgalemele": "A105",
        "Els": "A106",
        "Harle": "A107",
        "Mochabe": "A108",
        "Mdluli": "A109",
        "Maweni": "A110",
        "Ramphomane": "A111",
        "Meiring": "A112",
        "Coetzee": "A113",
        "Hibbert": "A114",
        "Ndimande": "A115",
        "Hibbard": "A117",
        "Engelbrecht": "A118",
        "van Wyk": "A120",
        "Shiell": "A121",
        "du Toit": "B001",
        "Sekhula": "B002",
        "Maass": "B003",
        "Polayya": "B101",
        "Maswanganyi": "B103",
        "Hlongwana": "C002",
        "Green": "D001",
        "Kraamwinkel": "D002",
        "Labuschagne": "PRINCIPAL",
        "Mogapi": "RECEPTION",
        "Korb": "A121",
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing assignments
        cursor.execute("DELETE FROM staff_venue WHERE tenant_id = ?", (TENANT_ID,))
        
        count = 0
        for surname, venue_code in staff_venue_map.items():
            # Find staff by surname
            cursor.execute("""
                SELECT id FROM staff WHERE tenant_id = ? AND surname = ?
            """, (TENANT_ID, surname))
            staff_row = cursor.fetchone()
            
            # Find venue by code
            cursor.execute("""
                SELECT id FROM venue WHERE tenant_id = ? AND venue_code = ?
            """, (TENANT_ID, venue_code))
            venue_row = cursor.fetchone()
            
            if staff_row and venue_row:
                cursor.execute("""
                    INSERT OR REPLACE INTO staff_venue (staff_id, venue_id, tenant_id)
                    VALUES (?, ?, ?)
                """, (staff_row['id'], venue_row['id'], TENANT_ID))
                count += 1
        
        conn.commit()
        return count


def seed_user_sessions():
    """Create magic link sessions for demo users."""
    
    sessions = [
        # (magic_code, surname_to_find, role, can_resolve)
        ("nadia", "Stoltz", "teacher", 0),
        ("pierre", "Labuschagne", "principal", 1),
        ("kea", "Mogapi", "deputy", 1),
        ("marielouise", "Korb", "deputy", 1),
        ("rianette", "van Vollenstee", "grade_head", 1),
        ("rika", "Badenhorst", "grade_head", 1),
        ("athanathi", "Maweni", "grade_head", 1),
        ("victor", "Nyoni", "grade_head", 1),
        ("bongi", "Mochabe", "grade_head", 1),
        ("admin", None, "admin", 1),  # Special admin user
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing sessions
        cursor.execute("DELETE FROM user_session WHERE tenant_id = ?", (TENANT_ID,))
        
        count = 0
        for magic_code, surname, role, can_resolve in sessions:
            session_id = generate_id()
            
            if surname:
                # Find staff by surname
                cursor.execute("""
                    SELECT id, display_name FROM staff WHERE tenant_id = ? AND surname = ?
                """, (TENANT_ID, surname))
                staff_row = cursor.fetchone()
                
                if staff_row:
                    cursor.execute("""
                        INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (session_id, TENANT_ID, staff_row['id'], magic_code, staff_row['display_name'], role, can_resolve))
                    count += 1
            else:
                # Admin user without staff link
                cursor.execute("""
                    INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, TENANT_ID, "ADMIN", magic_code, "Admin", role, can_resolve))
                count += 1
        
        conn.commit()
        return count


def seed_all_emergency():
    """Seed all emergency-related data."""
    results = {
        'venues': seed_venues(),
        'staff_venues': seed_staff_venues(),
        'user_sessions': seed_user_sessions(),
    }
    return results


if __name__ == "__main__":
    results = seed_all_emergency()
    print(f"Seeded: {results}")
