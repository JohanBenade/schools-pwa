"""
Admin routes - Attendance dashboard for office admin
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session
from datetime import date, datetime
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

TENANT_ID = "MARAGON"


def get_back_url_for_user():
    """Get appropriate back URL based on user role."""
    role = session.get('role', 'teacher')
    if role in ['principal', 'deputy', 'admin']:
        return '/dashboard/', 'Dashboard'
    return '/', 'Home'


@admin_bp.route('/')
def dashboard():
    """Main admin dashboard."""
    today = date.today()
    today_str = today.isoformat()
    today_display = today.strftime('%A, %d %B %Y')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                mg.id,
                mg.group_name,
                g.grade_name,
                g.grade_number,
                s.display_name as mentor_name,
                a.id as attendance_id,
                a.submitted_at,
                (SELECT COUNT(*) FROM learner l WHERE l.mentor_group_id = mg.id AND l.is_active = 1) as total_learners,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance att ON ae.attendance_id = att.id 
                 WHERE att.mentor_group_id = mg.id AND att.date = ? AND ae.status = 'Present') as present_count,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance att ON ae.attendance_id = att.id 
                 WHERE att.mentor_group_id = mg.id AND att.date = ? AND ae.status = 'Absent') as absent_count,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance att ON ae.attendance_id = att.id 
                 WHERE att.mentor_group_id = mg.id AND att.date = ? AND ae.status = 'Absent' AND ae.stasy_captured = 1) as captured_count,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance att ON ae.attendance_id = att.id 
                 WHERE att.mentor_group_id = mg.id AND att.date = ? AND ae.status = 'Late') as late_count
            FROM mentor_group mg
            LEFT JOIN grade g ON mg.grade_id = g.id
            LEFT JOIN staff s ON mg.mentor_id = s.id
            LEFT JOIN attendance a ON mg.id = a.mentor_group_id AND a.date = ?
            ORDER BY g.grade_number, mg.group_name
        ''', (today_str, today_str, today_str, today_str, today_str))
        
        groups = [dict(row) for row in cursor.fetchall()]
        
        total_groups = len(groups)
        submitted_count = sum(1 for g in groups if g['attendance_id'])
        pending_count = total_groups - submitted_count
        
        total_present = sum(g['present_count'] or 0 for g in groups)
        total_absent = sum(g['absent_count'] or 0 for g in groups)
        total_captured = sum(g['captured_count'] or 0 for g in groups)
        total_late = sum(g['late_count'] or 0 for g in groups)
        
        def sort_key(g):
            absent = g['absent_count'] or 0
            captured = g['captured_count'] or 0
            is_fully_captured = g['attendance_id'] and absent > 0 and captured == absent
            is_all_present = g['attendance_id'] and absent == 0
            is_done = is_fully_captured or is_all_present
            is_submitted_needs_action = g['attendance_id'] and absent > 0 and captured < absent
            is_pending = not g['attendance_id']
            
            if is_submitted_needs_action:
                priority = 0
            elif is_pending:
                priority = 1
            else:
                priority = 2
            
            return (priority, g['grade_number'] or 99, g['group_name'])
        
        groups = sorted(groups, key=sort_key)
    
    back_url, back_label = get_back_url_for_user()
    nav_header = get_nav_header("Attendance Admin", back_url, back_label)
    nav_styles = get_nav_styles()
    
    return render_template('admin/dashboard.html',
                          today_display=today_display,
                          groups=groups,
                          total_groups=total_groups,
                          submitted_count=submitted_count,
                          pending_count=pending_count,
                          total_present=total_present,
                          total_absent=total_absent,
                          total_captured=total_captured,
                          total_late=total_late,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@admin_bp.route('/absentees')
def absentees():
    """List all absent learners for STASY entry."""
    today = date.today()
    today_str = today.isoformat()
    today_display = today.strftime('%A, %d %B %Y')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                ae.id as entry_id,
                l.first_name,
                l.surname,
                mg.group_name,
                g.grade_name,
                ae.status,
                ae.stasy_captured
            FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            JOIN learner l ON ae.learner_id = l.id
            JOIN mentor_group mg ON a.mentor_group_id = mg.id
            LEFT JOIN grade g ON mg.grade_id = g.id
            WHERE a.date = ? AND ae.status IN ('Absent', 'Late')
            ORDER BY ae.stasy_captured ASC, l.surname, l.first_name
        ''', (today_str,))
        
        absentees = [dict(row) for row in cursor.fetchall()]
        
        total = len(absentees)
        captured = sum(1 for a in absentees if a['stasy_captured'])
    
    back_url, back_label = get_back_url_for_user()
    nav_header = get_nav_header("Absentees", "/admin/", "Admin")
    nav_styles = get_nav_styles()
    
    return render_template('admin/absentees.html',
                          today_display=today_display,
                          absentees=absentees,
                          total=total,
                          captured=captured,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@admin_bp.route('/late')
def late_learners():
    """List all late learners."""
    today = date.today()
    today_str = today.isoformat()
    today_display = today.strftime('%A, %d %B %Y')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                l.first_name,
                l.surname,
                mg.group_name,
                g.grade_name,
                ae.notes
            FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            JOIN learner l ON ae.learner_id = l.id
            JOIN mentor_group mg ON a.mentor_group_id = mg.id
            LEFT JOIN grade g ON mg.grade_id = g.id
            WHERE a.date = ? AND ae.status = 'Late'
            ORDER BY g.grade_number, mg.group_name, l.surname, l.first_name
        ''', (today_str,))
        
        late = [dict(row) for row in cursor.fetchall()]
    
    nav_header = get_nav_header("Late Arrivals", "/admin/", "Admin")
    nav_styles = get_nav_styles()
    
    return render_template('admin/late.html',
                          today_display=today_display,
                          late_learners=late,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@admin_bp.route('/class/<attendance_id>')
def class_detail(attendance_id):
    """View and edit attendance for a specific class."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT a.*, mg.group_name, g.grade_name, s.display_name as mentor_name
            FROM attendance a
            JOIN mentor_group mg ON a.mentor_group_id = mg.id
            LEFT JOIN grade g ON mg.grade_id = g.id
            LEFT JOIN staff s ON mg.mentor_id = s.id
            WHERE a.id = ?
        ''', (attendance_id,))
        row = cursor.fetchone()
        attendance = dict(row) if row else None
        
        if not attendance:
            return redirect(url_for('admin.dashboard'))
        
        att_date = datetime.strptime(attendance['date'], '%Y-%m-%d')
        attendance['date_display'] = att_date.strftime('%A, %d %B %Y')
        
        cursor.execute('''
            SELECT ae.id as entry_id, ae.learner_id, ae.status, ae.notes, ae.stasy_captured,
                   l.first_name, l.surname
            FROM attendance_entry ae
            JOIN learner l ON ae.learner_id = l.id
            WHERE ae.attendance_id = ?
            ORDER BY 
                CASE ae.status 
                    WHEN 'Absent' THEN 0 
                    WHEN 'Late' THEN 1 
                    ELSE 2 
                END,
                l.surname, l.first_name
        ''', (attendance_id,))
        entries = [dict(row) for row in cursor.fetchall()]
    
    nav_header = get_nav_header(attendance['group_name'], "/admin/", "Admin")
    nav_styles = get_nav_styles()
    
    return render_template('admin/class_detail.html',
                          attendance=attendance,
                          entries=entries,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@admin_bp.route('/override/<entry_id>', methods=['POST'])
def override_status(entry_id):
    """Admin override of learner status."""
    new_status = request.form.get('status')
    attendance_id = request.form.get('attendance_id')
    return_to = request.form.get('return_to', 'class')
    
    if new_status in ('Present', 'Absent', 'Late'):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT status FROM attendance_entry WHERE id = ?', (entry_id,))
            old = cursor.fetchone()
            
            if old and old['status'] == 'Absent' and new_status != 'Absent':
                cursor.execute('''
                    UPDATE attendance_entry
                    SET status = ?, stasy_captured = 0, stasy_captured_at = NULL
                    WHERE id = ?
                ''', (new_status, entry_id))
            else:
                cursor.execute('''
                    UPDATE attendance_entry
                    SET status = ?
                    WHERE id = ?
                ''', (new_status, entry_id))
            conn.commit()
    
    if return_to == 'absentees':
        return redirect(url_for('admin.absentees'))
    return redirect(url_for('admin.class_detail', attendance_id=attendance_id))


@admin_bp.route('/capture/<entry_id>', methods=['POST'])
def capture_entry(entry_id):
    """Mark single learner as captured in STASY."""
    return_to = request.form.get('return_to', 'absentees')
    attendance_id = request.form.get('attendance_id')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE attendance_entry
            SET stasy_captured = 1, stasy_captured_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), entry_id))
        conn.commit()
    
    if return_to == 'class' and attendance_id:
        return redirect(url_for('admin.class_detail', attendance_id=attendance_id))
    return redirect(url_for('admin.absentees'))


@admin_bp.route('/uncapture/<entry_id>', methods=['POST'])
def uncapture_entry(entry_id):
    """Undo STASY capture for a learner."""
    return_to = request.form.get('return_to', 'absentees')
    attendance_id = request.form.get('attendance_id')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE attendance_entry
            SET stasy_captured = 0, stasy_captured_at = NULL
            WHERE id = ?
        ''', (entry_id,))
        conn.commit()
    
    if return_to == 'class' and attendance_id:
        return redirect(url_for('admin.class_detail', attendance_id=attendance_id))
    return redirect(url_for('admin.absentees'))


# ============================================
# SEED AND DEBUG ENDPOINTS (keeping all existing ones)
# ============================================

@admin_bp.route('/seed-data', methods=['GET', 'POST'])
def seed_data():
    if request.method == 'GET':
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM staff")
            staff_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM mentor_group")
            mg_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM learner")
            learner_count = cursor.fetchone()[0]
        
        return f'''
        <html><head><title>Seed Data</title>
        <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
        .warning {{ background: #fee; border: 1px solid #c00; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        .current {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        button {{ background: #c00; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; }}
        a {{ color: #007AFF; }}</style></head>
        <body><h1>Seed Maragon Data</h1>
        <div class="current"><h3>Current Data</h3><p>Staff: {staff_count}</p><p>Mentor Groups: {mg_count}</p><p>Learners: {learner_count}</p></div>
        <div class="warning"><h3>Warning</h3><p>This will DELETE all existing data.</p></div>
        <form method="POST"><button type="submit">Seed Data Now</button></form>
        <p style="margin-top: 2rem;"><a href="/admin/">Back to Dashboard</a></p></body></html>
        '''
    
    from app.services.seed_maragon_data import seed_all
    result = seed_all()
    return f'<html><body><h1>Seed Complete</h1><p>Staff: {result["staff"]}</p><p>Mentor Groups: {result["mentor_groups"]}</p><p>Learners: {result["learners"]}</p><p><a href="/admin/">Go to Dashboard</a></p></body></html>'


@admin_bp.route('/db-stats')
def db_stats():
    with get_connection() as conn:
        cursor = conn.cursor()
        stats = {}
        for table in ['staff', 'mentor_group', 'learner', 'grade', 'attendance', 'attendance_entry']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
    return jsonify(stats)


@admin_bp.route('/seed-emergency', methods=['GET', 'POST'])
def seed_emergency():
    if request.method == 'GET':
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM venue WHERE tenant_id = 'MARAGON'")
            venue_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM user_session WHERE tenant_id = 'MARAGON'")
            session_count = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='push_token'")
            push_table_exists = cursor.fetchone() is not None
        
        return f'''<html><head><title>Seed Emergency Data</title>
        <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
        .info {{ background: #e0f2fe; border: 1px solid #0284c7; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        .current {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        button {{ background: #3b82f6; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; cursor: pointer; }}
        a {{ color: #007AFF; }}</style></head>
        <body><h1>Seed Emergency Data</h1>
        <div class="current"><h3>Current</h3><p>Venues: {venue_count}</p><p>Sessions: {session_count}</p><p>Push Table: {'✅' if push_table_exists else '❌'}</p></div>
        <form method="POST"><button type="submit">Seed Emergency Data</button></form>
        <p style="margin-top: 2rem;"><a href="/admin/">Back</a></p></body></html>'''
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS push_token (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, staff_id TEXT, token TEXT NOT NULL UNIQUE, device_info TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), last_used_at TEXT)''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_tenant ON push_token(tenant_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_staff ON push_token(staff_id)')
        conn.commit()
    
    from app.services.seed_emergency_data import seed_all_emergency
    result = seed_all_emergency()
    return f'<html><body><h1>Done</h1><p>Venues: {result["venues"]}</p><p><a href="/">Home</a></p></body></html>'


@admin_bp.route('/init-push')
def init_push():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS push_token (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, staff_id TEXT, token TEXT NOT NULL UNIQUE, device_info TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')), last_used_at TEXT)''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_tenant ON push_token(tenant_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_staff ON push_token(staff_id)')
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM push_token")
        token_count = cursor.fetchone()[0]
    return jsonify({'success': True, 'registered_tokens': token_count})


@admin_bp.route('/seed-substitute', methods=['GET', 'POST'])
def seed_substitute():
    if request.method == 'GET':
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM period WHERE tenant_id = 'MARAGON'")
            period_count = cursor.fetchone()[0]
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timetable_slot'")
            timetable_exists = cursor.fetchone() is not None
            slot_count = 0
            if timetable_exists:
                cursor.execute("SELECT COUNT(*) FROM timetable_slot WHERE tenant_id = 'MARAGON'")
                slot_count = cursor.fetchone()[0]
        return f'''<html><head><title>Seed Substitute</title><style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }} button {{ background: #f97316; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; cursor: pointer; }} a {{ color: #007AFF; }}</style></head><body><h1>Seed Substitute Data</h1><p>Periods: {period_count}, Slots: {slot_count}</p><form method="POST"><button type="submit">Seed</button></form><p><a href="/admin/">Back</a></p></body></html>'''
    
    from app.services.seed_substitute_data import seed_all_substitute
    result = seed_all_substitute()
    return f'<html><body><h1>Done</h1><p>Periods: {result["periods"]}, Slots: {result["timetable_slots"]}</p><p><a href="/admin/">Back</a></p></body></html>'


@admin_bp.route('/setup-substitute-demo')
def setup_substitute_demo():
    import uuid
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, display_name FROM staff WHERE surname = 'du Toit' AND tenant_id = 'MARAGON'")
        beatrix = cursor.fetchone()
        results = {'beatrix': None, 'sessions_created': []}
        if beatrix:
            results['beatrix'] = dict(beatrix)
            cursor.execute("SELECT * FROM user_session WHERE magic_code = 'beatrix'")
            existing = cursor.fetchone()
            if not existing:
                cursor.execute("INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve) VALUES (?, 'MARAGON', ?, 'beatrix', ?, 'teacher', 0)", (str(uuid.uuid4()), beatrix['id'], beatrix['display_name']))
                results['sessions_created'].append('beatrix')
        cursor.execute("UPDATE user_session SET role = 'principal', can_resolve = 1 WHERE magic_code = 'pierre'")
        cursor.execute("UPDATE user_session SET role = 'admin', can_resolve = 1 WHERE magic_code = 'admin'")
        conn.commit()
        cursor.execute("SELECT magic_code, display_name, role FROM user_session WHERE tenant_id = 'MARAGON'")
        results['all_sessions'] = [dict(row) for row in cursor.fetchall()]
    return jsonify(results)


@admin_bp.route('/reset-substitute-test')
def reset_substitute_test():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM substitute_request WHERE tenant_id = 'MARAGON'")
        cursor.execute("DELETE FROM absence WHERE tenant_id = 'MARAGON'")
        cursor.execute("DELETE FROM substitute_log WHERE tenant_id = 'MARAGON'")
        cursor.execute("UPDATE substitute_config SET pointer_surname = 'A', pointer_updated_at = datetime('now') WHERE tenant_id = 'MARAGON'")
        conn.commit()
    return jsonify({'success': True, 'message': 'Substitute test data cleared, pointer reset to A'})


@admin_bp.route('/add-johan')
def add_johan():
    import uuid
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM staff WHERE surname = 'Benade' AND tenant_id = 'MARAGON'")
        existing_staff = cursor.fetchone()
        if existing_staff:
            staff_id = existing_staff['id']
        else:
            staff_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, staff_type, can_substitute, is_active) VALUES (?, 'MARAGON', 'Mr', 'Johan', 'Benade', 'Mr Johan', 'Admin', 0, 1)", (staff_id,))
        cursor.execute("SELECT id FROM venue WHERE venue_code = 'Z999' AND tenant_id = 'MARAGON'")
        existing_venue = cursor.fetchone()
        if existing_venue:
            venue_id = existing_venue['id']
        else:
            venue_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO venue (id, tenant_id, venue_code, venue_name, venue_type, block, sort_order, is_active) VALUES (?, 'MARAGON', 'Z999', 'Z999 - Mr Johan', 'office', 'Admin', 999, 1)", (venue_id,))
        cursor.execute("DELETE FROM staff_venue WHERE staff_id = ?", (staff_id,))
        cursor.execute("INSERT INTO staff_venue (staff_id, venue_id, tenant_id) VALUES (?, ?, 'MARAGON')", (staff_id, venue_id))
        cursor.execute("DELETE FROM user_session WHERE magic_code = 'johan'")
        cursor.execute("INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve) VALUES (?, 'MARAGON', ?, 'johan', 'Mr Johan', 'admin', 1)", (str(uuid.uuid4()), staff_id))
        conn.commit()
    return jsonify({'success': True, 'magic_link': 'https://schoolops.co.za/?u=johan'})


@admin_bp.route('/add-bongi')
def add_bongi():
    import uuid
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, display_name FROM staff WHERE surname = 'Mochabe' AND tenant_id = 'MARAGON'")
        staff = cursor.fetchone()
        if not staff:
            return jsonify({'error': 'Bongi not found'})
        cursor.execute("DELETE FROM user_session WHERE magic_code = 'bongi'")
        cursor.execute("INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve) VALUES (?, 'MARAGON', ?, 'bongi', ?, 'grade_head', 1)", (str(uuid.uuid4()), staff['id'], staff['display_name']))
        conn.commit()
    return jsonify({'success': True, 'magic_link': 'https://schoolops.co.za/?u=bongi'})


@admin_bp.route('/add-deputies')
def add_deputies():
    import uuid
    results = {'added': [], 'errors': []}
    deputies = [{'surname': 'Mogapi', 'magic_code': 'kea'}, {'surname': 'Korb', 'magic_code': 'marielouise'}]
    with get_connection() as conn:
        cursor = conn.cursor()
        for dep in deputies:
            cursor.execute("SELECT id, display_name FROM staff WHERE surname = ? AND tenant_id = 'MARAGON'", (dep['surname'],))
            staff = cursor.fetchone()
            if not staff:
                results['errors'].append(f"{dep['surname']} not found")
                continue
            cursor.execute("SELECT id FROM user_session WHERE magic_code = ?", (dep['magic_code'],))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE user_session SET staff_id = ?, display_name = ?, role = 'deputy', can_resolve = 1 WHERE magic_code = ?", (staff['id'], staff['display_name'], dep['magic_code']))
            else:
                cursor.execute("INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve) VALUES (?, 'MARAGON', ?, ?, ?, 'deputy', 1)", (str(uuid.uuid4()), staff['id'], dep['magic_code'], staff['display_name']))
            results['added'].append({'name': staff['display_name'], 'magic_link': f"https://schoolops.co.za/?u={dep['magic_code']}"})
        conn.commit()
    return jsonify(results)
