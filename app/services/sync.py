"""
Sync reference data from Notion to SQLite.
Run once at startup, or manually when school data changes.
"""

import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from app.services.notion import (
    get_mentor_groups as notion_get_mentor_groups,
    get_all_staff as notion_get_all_staff,
    get_all_grades as notion_get_all_grades,
)
from app.services.notion import _query_database, _parse_page

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'schoolops.db')
TENANT_ID = "MARAGON"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_mentor_groups():
    print("Syncing mentor groups...")
    groups = notion_get_mentor_groups()
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    for g in groups:
        cursor.execute('''
            INSERT OR REPLACE INTO mentor_group 
            (id, tenant_id, group_name, mentor_id, grade_id, venue_id, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            g['id'], TENANT_ID, g.get('group_name'), g.get('mentor_id'), g.get('grade_id'),
            g.get('venue_id')[0] if isinstance(g.get('venue_id'), list) and g.get('venue_id') else None, now
        ))
    
    conn.commit()
    conn.close()
    print(f"  Synced {len(groups)} mentor groups")
    return len(groups)


def sync_learners():
    print("Syncing learners...")
    property_map = {
        "first_name": "first_name", "surname": "surname", "grade_id": "grade_id",
        "mentor_group_id": "mentor_group_id", "house_id": "house_id", "is_active": "is_active"
    }
    filter_obj = {"property": "is_active", "checkbox": {"equals": True}}
    db_id = os.environ.get('NOTION_DB_LEARNER', '')
    results = _query_database(db_id, filter_obj)
    
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    count = 0
    
    for page in results:
        parsed = _parse_page(page, property_map)
        for field in ["grade_id", "mentor_group_id", "house_id"]:
            if parsed.get(field) and isinstance(parsed[field], list):
                parsed[field] = parsed[field][0] if parsed[field] else None
        
        cursor.execute('''
            INSERT OR REPLACE INTO learner
            (id, tenant_id, first_name, surname, grade_id, mentor_group_id, house_id, is_active, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            parsed['id'], TENANT_ID, parsed.get('first_name'), parsed.get('surname'),
            parsed.get('grade_id'), parsed.get('mentor_group_id'), parsed.get('house_id'),
            1 if parsed.get('is_active') else 0, now
        ))
        count += 1
    
    conn.commit()
    conn.close()
    print(f"  Synced {count} learners")
    return count


def sync_staff():
    print("Syncing staff...")
    staff_list = notion_get_all_staff(active_only=True)
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    for s in staff_list:
        cursor.execute('''
            INSERT OR REPLACE INTO staff
            (id, tenant_id, title, first_name, surname, display_name, email, staff_type, can_substitute, can_do_duty, is_active, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            s['id'], TENANT_ID, s.get('title'), s.get('first_name'), s.get('surname'),
            s.get('display_name'), s.get('email'), s.get('staff_type'),
            1 if s.get('can_substitute') else 0, 1 if s.get('can_do_duty') else 0,
            1 if s.get('is_active') else 0, now
        ))
    
    conn.commit()
    conn.close()
    print(f"  Synced {len(staff_list)} staff members")
    return len(staff_list)


def sync_grades():
    print("Syncing grades...")
    grades = notion_get_all_grades()
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    
    for g in grades:
        cursor.execute('''
            INSERT OR REPLACE INTO grade
            (id, tenant_id, grade_name, grade_code, grade_number, sort_order, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            g['id'], TENANT_ID, g.get('grade_name'), g.get('grade_code'),
            g.get('grade_number'), g.get('sort_order'), now
        ))
    
    conn.commit()
    conn.close()
    print(f"  Synced {len(grades)} grades")
    return len(grades)


def sync_all():
    print("=" * 50)
    print("SYNCING REFERENCE DATA: Notion -> SQLite")
    print("=" * 50)
    
    conn = get_db()
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql'), 'r') as f:
        conn.executescript(f.read())
    conn.close()
    
    results = {
        'grades': sync_grades(),
        'mentor_groups': sync_mentor_groups(),
        'staff': sync_staff(),
        'learners': sync_learners(),
    }
    
    print("=" * 50)
    print("SYNC COMPLETE")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("=" * 50)
    return results


if __name__ == "__main__":
    sync_all()
