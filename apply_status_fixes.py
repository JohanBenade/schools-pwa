#!/usr/bin/env python3
"""
SchoolOps Status Page Fixes 1-4
Run from: ~/Documents/GitHub/schools-pwa
"""
import os

REPO = os.path.expanduser("~/Documents/GitHub/schools-pwa")
SUB_PY = os.path.join(REPO, "app/routes/substitute.py")
STATUS_HTML = os.path.join(REPO, "app/templates/substitute/status.html")

# ============================================================
# FIX: Replace absence_status route in substitute.py
# Fixes 1 (duplicate terrain), 2 prep, 3 (mentor name), 4 (back nav)
# ============================================================

OLD_ROUTE = '''@substitute_bp.route('/status/<absence_id>')
def absence_status(absence_id):
    """View status of an absence."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            WHERE a.id = ?
        """, (absence_id,))
        absence = cursor.fetchone()
        if not absence:
            return "Absence not found", 404
        absence = dict(absence)
        
        cursor.execute("""
            SELECT sr.*, p.period_name, p.period_number, p.start_time, p.end_time,
                   sub.display_name as substitute_name
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            LEFT JOIN staff sub ON sr.substitute_id = sub.id
            WHERE sr.absence_id = ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        """, (absence_id,))
        requests = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("""
            SELECT * FROM substitute_log
            WHERE absence_id = ?
            ORDER BY created_at ASC
        """, (absence_id,))
        events = [dict(row) for row in cursor.fetchall()]
    
    return render_template('substitute/status.html',
                          absence=absence,
                          requests=requests,
                          events=events)'''

NEW_ROUTE = """@substitute_bp.route('/status/<absence_id>')
def absence_status(absence_id):
    \"\"\"View status of an absence - summary cards.\"\"\"
    import json

    staff_id = session.get('staff_id')
    role = session.get('role', 'teacher')

    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Get absence record
        cursor.execute(\"\"\"
            SELECT a.*, s.display_name as teacher_name
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            WHERE a.id = ?
        \"\"\", (absence_id,))
        absence = cursor.fetchone()
        if not absence:
            return "Absence not found", 404
        absence = dict(absence)

        # Format dates for display
        try:
            absence['start_display'] = datetime.strptime(absence['absence_date'], '%Y-%m-%d').strftime('%a %d %b')
        except (ValueError, TypeError):
            absence['start_display'] = absence.get('absence_date', '')
        if absence.get('end_date'):
            try:
                absence['end_display'] = datetime.strptime(absence['end_date'], '%Y-%m-%d').strftime('%a %d %b')
            except (ValueError, TypeError):
                absence['end_display'] = absence.get('end_date', '')

        is_own = (absence['staff_id'] == staff_id)
        is_resolved = absence.get('returned_early') == 1 or absence.get('status') == 'Resolved'

        # 2. Return info (if marked back)
        return_info = None
        if is_resolved:
            cursor.execute(\"\"\"
                SELECT details FROM substitute_log
                WHERE absence_id = ? AND event_type IN ('early_return', 'mark_back')
                ORDER BY created_at DESC LIMIT 1
            \"\"\", (absence_id,))
            log_row = cursor.fetchone()
            if log_row and log_row['details']:
                try:
                    return_info = json.loads(log_row['details'])
                except (json.JSONDecodeError, TypeError):
                    return_info = {'return_date': absence.get('end_date', '')}
            else:
                return_info = {'return_date': absence.get('end_date', '')}
            # Format return date for display
            if return_info.get('return_date'):
                try:
                    return_info['return_date'] = datetime.strptime(
                        return_info['return_date'], '%Y-%m-%d'
                    ).strftime('%a %d %b')
                except (ValueError, TypeError):
                    pass

        # 3. Get substitute requests (teaching + mentor)
        cursor.execute(\"\"\"
            SELECT sr.*, p.period_name, p.period_number, p.start_time, p.end_time,
                   sub.display_name as substitute_name,
                   v_mg.venue_code as mentor_venue
            FROM substitute_request sr
            LEFT JOIN period p ON sr.period_id = p.id
            LEFT JOIN staff sub ON sr.substitute_id = sub.id
            LEFT JOIN absence a2 ON sr.absence_id = a2.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = a2.staff_id
            LEFT JOIN venue v_mg ON mg.venue_id = v_mg.id
            WHERE sr.absence_id = ?
            ORDER BY sr.request_date, sr.is_mentor_duty DESC, p.sort_order
        \"\"\", (absence_id,))
        requests = [dict(row) for row in cursor.fetchall()]

        # 4. Split into mentor and teaching periods
        mentor_info = None
        teaching_periods = []

        for req in requests:
            if req.get('is_mentor_duty'):
                mentor_info = {
                    'status': req['status'],
                    'substitute_name': req.get('substitute_name'),
                    'venue': req.get('mentor_venue') or req.get('venue_name')
                }
            else:
                teaching_periods.append(req)

        # 5. Teaching period stats
        periods_cancelled = len([p for p in teaching_periods if p['status'] == 'Cancelled'])
        active_periods = [p for p in teaching_periods if p['status'] != 'Cancelled']
        periods_total = len(active_periods)
        periods_covered = len([p for p in active_periods if p.get('substitute_id')])
        uncovered = [
            {'period_name': p.get('period_name', 'Unknown'), 'class_name': p.get('class_name', '')}
            for p in active_periods if not p.get('substitute_id')
        ]

        # 6. Terrain + homework duties
        terrain_duties = []
        homework_duties = []
        absent_staff_id = absence['staff_id']
        abs_start = absence['absence_date']
        abs_end = absence.get('end_date') or absence['absence_date']

        if not is_resolved:
            # Active absence: get from duty_roster where replacement_id is set
            cursor.execute(\"\"\"
                SELECT dr.duty_type, ta.area_name, rep.display_name as replacement_name
                FROM duty_roster dr
                LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
                LEFT JOIN staff rep ON dr.replacement_id = rep.id
                WHERE dr.staff_id = ? AND dr.replacement_id IS NOT NULL
                  AND dr.duty_date >= ? AND dr.duty_date <= ?
            \"\"\", (absent_staff_id, abs_start, abs_end))

            for row in cursor.fetchall():
                row = dict(row)
                if row['duty_type'] == 'terrain':
                    terrain_duties.append({
                        'area_name': row.get('area_name', 'Terrain'),
                        'replacement_name': row.get('replacement_name'),
                        'was_restored': False
                    })
                elif row['duty_type'] == 'homework':
                    homework_duties.append({
                        'replacement_name': row.get('replacement_name'),
                        'was_restored': False
                    })
        else:
            # Resolved: fall back to duty_decline (Fix 1: GROUP BY to avoid duplicates)
            cursor.execute(\"\"\"
                SELECT dd.duty_type, dd.duty_description, MIN(dd.duty_date) as duty_date
                FROM duty_decline dd
                WHERE dd.staff_id = ? AND dd.reason = 'absent'
                  AND dd.duty_date >= ? AND dd.duty_date <= ?
                GROUP BY dd.duty_type, dd.duty_date
                ORDER BY dd.duty_date
            \"\"\", (absent_staff_id, abs_start, abs_end))

            # Check if return_info has captured replacement names (Fix 2 prep)
            restored_duties = []
            if return_info and isinstance(return_info, dict):
                restored_duties = return_info.get('duties_restored', [])

            for row in cursor.fetchall():
                row = dict(row)
                # Try to find replacement name from return_info snapshot
                rep_name = None
                for snap in restored_duties:
                    if snap.get('duty_type') == row['duty_type']:
                        rep_name = snap.get('replacement_name')
                        break

                if row['duty_type'] == 'terrain':
                    terrain_duties.append({
                        'area_name': row.get('duty_description', 'Terrain'),
                        'replacement_name': rep_name,
                        'was_restored': True
                    })
                elif row['duty_type'] == 'homework':
                    homework_duties.append({
                        'replacement_name': rep_name,
                        'was_restored': True
                    })

    return render_template('substitute/status.html',
                          absence=absence,
                          return_info=return_info,
                          periods_covered=periods_covered,
                          periods_total=periods_total,
                          periods_cancelled=periods_cancelled,
                          uncovered=uncovered,
                          mentor_info=mentor_info,
                          terrain_duties=terrain_duties,
                          homework_duties=homework_duties,
                          is_own=is_own,
                          role=role)"""

# ============================================================
# FIX 3: Template - show mentor name even when cancelled
# ============================================================

OLD_MENTOR_TEMPLATE = """                    {% if mentor_info.status == 'Cancelled' %}Cancelled
                    {% elif mentor_info.substitute_name %}{{ mentor_info.substitute_name }}{% if mentor_info.venue %} → {{ mentor_info.venue }}{% endif %}
                    {% else %}Unassigned{% endif %}"""

NEW_MENTOR_TEMPLATE = """                    {% if mentor_info.status == 'Cancelled' %}{% if mentor_info.substitute_name %}{{ mentor_info.substitute_name }} (cancelled){% else %}Cancelled{% endif %}
                    {% elif mentor_info.substitute_name %}{{ mentor_info.substitute_name }}{% if mentor_info.venue %} → {{ mentor_info.venue }}{% endif %}
                    {% else %}Unassigned{% endif %}"""


def apply_fixes():
    # Verify files exist
    for f in [SUB_PY, STATUS_HTML]:
        if not os.path.exists(f):
            print(f"ERROR: File not found: {f}")
            return False

    # Fix substitute.py - replace absence_status route
    with open(SUB_PY, 'r') as f:
        content = f.read()

    if OLD_ROUTE not in content:
        print("WARNING: Could not find old absence_status route in substitute.py")
        print("The route may have already been updated, or the code has changed.")
        print("Skipping substitute.py changes.")
    else:
        content = content.replace(OLD_ROUTE, NEW_ROUTE)
        with open(SUB_PY, 'w') as f:
            f.write(content)
        print("✅ substitute.py: absence_status route replaced")

    # Fix status.html - mentor name on cancelled
    with open(STATUS_HTML, 'r') as f:
        html = f.read()

    if OLD_MENTOR_TEMPLATE in html:
        html = html.replace(OLD_MENTOR_TEMPLATE, NEW_MENTOR_TEMPLATE)
        with open(STATUS_HTML, 'w') as f:
            f.write(html)
        print("✅ status.html: Fix 3 - mentor name on cancelled applied")
    else:
        print("WARNING: Could not find mentor template text in status.html")

    print("\n✅ All fixes applied. Ready to commit.")
    return True


if __name__ == '__main__':
    apply_fixes()
