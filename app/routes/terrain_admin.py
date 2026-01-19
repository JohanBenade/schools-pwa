"""
Terrain duty generation - admin routes
"""

from flask import Blueprint, jsonify
from datetime import date, timedelta
from app.services.db import get_connection
import uuid

terrain_admin_bp = Blueprint('terrain_admin', __name__, url_prefix='/admin/terrain')

TENANT_ID = "MARAGON"


@terrain_admin_bp.route('/generate-week')
def generate_week():
    """Generate terrain + homework duties for current week (Mon-Fri)."""
    
    results = {'cleared': 0, 'terrain': [], 'homework': [], 'staff': [], 'errors': []}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Step 1: Clear existing duties
        cursor.execute("DELETE FROM duty_roster WHERE tenant_id = ?", (TENANT_ID,))
        results['cleared'] = cursor.rowcount
        
        # Step 2: Get eligible staff sorted alphabetically by first name
        cursor.execute("""
            SELECT id, display_name, first_name, surname
            FROM staff
            WHERE tenant_id = ? AND can_do_duty = 1 AND is_active = 1
            ORDER BY first_name ASC, surname ASC
        """, (TENANT_ID,))
        staff = [dict(row) for row in cursor.fetchall()]
        results['staff'] = [s['display_name'] for s in staff]
        
        if not staff:
            results['errors'].append('No eligible staff found')
            return jsonify(results)
        
        # Step 3: Get terrain areas (exclude homework)
        cursor.execute("""
            SELECT id, area_name
            FROM terrain_area
            WHERE tenant_id = ? AND is_active = 1 AND area_name NOT LIKE '%Homework%'
            ORDER BY sort_order
        """, (TENANT_ID,))
        areas = [dict(row) for row in cursor.fetchall()]
        
        if not areas:
            results['errors'].append('No terrain areas found')
            return jsonify(results)
        
        # Step 4: Get current week Mon-Fri
        today = date.today()
        weekday = today.weekday()
        if weekday == 5:
            monday = today + timedelta(days=2)
        elif weekday == 6:
            monday = today + timedelta(days=1)
        else:
            monday = today - timedelta(days=weekday)
        
        week_days = [monday + timedelta(days=i) for i in range(5)]
        homework_days = week_days[:4]
        
        # Step 5: Generate terrain duties and track assigned staff
        terrain_pointer = 0
        staff_count = len(staff)
        terrain_assigned_ids = set()
        
        for day in week_days:
            day_str = day.isoformat()
            day_label = day.strftime('%a %d')
            
            for i, area in enumerate(areas):
                staff_idx = (terrain_pointer + i) % staff_count
                assigned = staff[staff_idx]
                terrain_assigned_ids.add(assigned['id'])
                
                duty_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO duty_roster (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status)
                    VALUES (?, ?, ?, ?, ?, 'terrain', 'Scheduled')
                """, (duty_id, TENANT_ID, day_str, area['id'], assigned['id']))
                
                results['terrain'].append(f"{day_label}: {area['area_name']} -> {assigned['display_name']}")
            
            terrain_pointer = (terrain_pointer + len(areas)) % staff_count
        
        # Step 6: Generate homework duties - skip anyone with terrain this week
        # Build list of staff NOT on terrain duty
        homework_eligible = [s for s in staff if s['id'] not in terrain_assigned_ids]
        
        if len(homework_eligible) < 4:
            results['errors'].append(f'Only {len(homework_eligible)} staff available for homework (need 4)')
            # Fall back to full list if not enough
            homework_eligible = staff
        
        results['homework_pool'] = [s['display_name'] for s in homework_eligible]
        
        homework_pointer = 0
        for day in homework_days:
            day_str = day.isoformat()
            day_label = day.strftime('%a %d')
            assigned = homework_eligible[homework_pointer % len(homework_eligible)]
            
            duty_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO duty_roster (id, tenant_id, duty_date, terrain_area_id, staff_id, duty_type, status)
                VALUES (?, ?, ?, NULL, ?, 'homework', 'Scheduled')
            """, (duty_id, TENANT_ID, day_str, assigned['id']))
            
            results['homework'].append(f"{day_label}: {assigned['display_name']}")
            homework_pointer = (homework_pointer + 1) % len(homework_eligible)
        
        # Step 7: Update pointers
        cursor.execute("""
            UPDATE terrain_config 
            SET pointer_index = ?, homework_pointer_index = ?, updated_at = datetime('now')
            WHERE tenant_id = ?
        """, (terrain_pointer, homework_pointer, TENANT_ID))
        
        results['pointers'] = {'terrain': terrain_pointer, 'homework': homework_pointer}
        results['week'] = f"{monday.strftime('%d %b')} - {(monday + timedelta(days=4)).strftime('%d %b %Y')}"
        results['terrain_count'] = len(terrain_assigned_ids)
        
        conn.commit()
    
    return jsonify(results)
