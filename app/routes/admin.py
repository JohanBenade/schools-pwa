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
        return '/', 'Home'
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
            ORDER BY ae.stasy_captured ASC, l.first_name, l.surname
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
            ORDER BY g.grade_number, mg.group_name, l.first_name, l.surname
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
                l.first_name, l.surname
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


@admin_bp.route('/generate-duties')
def generate_duties():
    """Generate terrain and homework duties for the next 5 school days."""
    from app.services.duty_generator import generate_all_duties
    result = generate_all_duties(TENANT_ID, days=5)
    return jsonify(result)


@admin_bp.route('/view-duties')
def view_duties():
    """View generated duties."""
    from datetime import timedelta
    today = date.today()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get terrain duties for next 7 days
        cursor.execute('''
            SELECT dr.duty_date, dr.duty_type, s.display_name, ta.area_name
            FROM duty_roster dr
            JOIN staff s ON dr.staff_id = s.id
            LEFT JOIN terrain_area ta ON dr.terrain_area_id = ta.id
            WHERE dr.tenant_id = ? AND dr.duty_date >= ?
            ORDER BY dr.duty_date ASC, dr.duty_type ASC, ta.sort_order ASC
        ''', (TENANT_ID, today.isoformat()))
        
        duties = [dict(row) for row in cursor.fetchall()]
        
        # Get pointers
        cursor.execute('SELECT pointer_index, homework_pointer_index FROM terrain_config WHERE tenant_id = ?', (TENANT_ID,))
        config = cursor.fetchone()
        
        # Get staff count for context
        cursor.execute('SELECT COUNT(*) FROM staff WHERE tenant_id = ? AND is_active = 1 AND can_do_duty = 1', (TENANT_ID,))
        staff_count = cursor.fetchone()[0]
    
    return jsonify({
        'duties': duties,
        'terrain_pointer': config['pointer_index'] if config else 0,
        'homework_pointer': config['homework_pointer_index'] if config else 0,
        'eligible_staff_count': staff_count
    })


@admin_bp.route('/add-test-users')
def add_test_users():
    """Add test users for duty testing."""
    from app.services.db import get_connection
    import uuid
    
    added = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        test_users = ['Chelsea', 'Thycha', 'Rika', 'Daleen', 'Anike']
        
        for name in test_users:
            cursor.execute("SELECT id, display_name FROM staff WHERE display_name LIKE ? AND tenant_id = 'MARAGON'", (f'%{name}%',))
            staff = cursor.fetchone()
            
            if not staff:
                continue
            
            magic_code = name.lower()
            
            cursor.execute("SELECT id FROM user_session WHERE magic_code = ? AND tenant_id = 'MARAGON'", (magic_code,))
            if cursor.fetchone():
                continue
            
            cursor.execute("""
                INSERT INTO user_session (id, tenant_id, staff_id, display_name, role, magic_code, can_resolve, created_at)
                VALUES (?, 'MARAGON', ?, ?, 'teacher', ?, 0, datetime('now'))
            """, (str(uuid.uuid4()), staff['id'], staff['display_name'], magic_code))
            
            added.append(magic_code)
        
        conn.commit()
    
    return jsonify({'added': added, 'message': f'Added {len(added)} test users'})


@admin_bp.route('/import-timetable')
def import_timetable():
    """Import timetable data from timetable_data.py"""
    from app.services.timetable_data import STAFF_HOME_ROOMS, TIMETABLE_SLOTS
    import uuid
    
    results = {
        'home_rooms_set': 0,
        'slots_imported': 0,
        'errors': []
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for magic_code, home_room in STAFF_HOME_ROOMS.items():
            if not home_room:
                continue
            
            cursor.execute(
                "SELECT staff_id FROM user_session WHERE magic_code = ? AND tenant_id = 'MARAGON'",
                (magic_code,)
            )
            row = cursor.fetchone()
            if not row:
                results['errors'].append(f"No user_session for {magic_code}")
                continue
            staff_id = row['staff_id']
            
            cursor.execute(
                "SELECT id FROM venue WHERE venue_code = ? AND tenant_id = 'MARAGON'",
                (home_room,)
            )
            row = cursor.fetchone()
            if not row:
                results['errors'].append(f"No venue {home_room} for {magic_code}")
                continue
            venue_id = row['id']
            
            cursor.execute(
                "DELETE FROM staff_venue WHERE staff_id = ? AND tenant_id = 'MARAGON'",
                (staff_id,)
            )
            cursor.execute(
                "INSERT INTO staff_venue (staff_id, venue_id, tenant_id) VALUES (?, ?, 'MARAGON')",
                (staff_id, venue_id)
            )
            results['home_rooms_set'] += 1
        
        cursor.execute("DELETE FROM timetable_slot WHERE tenant_id = 'MARAGON'")
        
        for magic_code, slots in TIMETABLE_SLOTS.items():
            cursor.execute(
                "SELECT staff_id FROM user_session WHERE magic_code = ? AND tenant_id = 'MARAGON'",
                (magic_code,)
            )
            row = cursor.fetchone()
            if not row:
                continue
            staff_id = row['staff_id']
            
            for day, period, subject, grade, class_code, venue in slots:
                cursor.execute(
                    "SELECT id FROM period WHERE period_number = ? AND tenant_id = 'MARAGON'",
                    (period,)
                )
                period_row = cursor.fetchone()
                if not period_row:
                    continue
                period_id = period_row['id']
                
                venue_id = None
                if venue:
                    cursor.execute(
                        "SELECT id FROM venue WHERE venue_code = ? AND tenant_id = 'MARAGON'",
                        (venue,)
                    )
                    venue_row = cursor.fetchone()
                    if venue_row:
                        venue_id = venue_row['id']
                
                class_name = f"Gr{grade} {class_code}"
                
                cursor.execute('''
                    INSERT INTO timetable_slot 
                    (id, tenant_id, staff_id, cycle_day, period_id, class_name, subject, venue_id)
                    VALUES (?, 'MARAGON', ?, ?, ?, ?, ?, ?)
                ''', (str(uuid.uuid4()), staff_id, day, period_id, class_name, subject, venue_id))
                
                results['slots_imported'] += 1
        
        conn.commit()
    
    errors_html = ''
    if results['errors']:
        errors_html = '<div class="errors"><h3>Errors</h3><ul>' + ''.join(f'<li>{e}</li>' for e in results['errors']) + '</ul></div>'
    
    return f'''
    <html><head><title>Timetable Import</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
    .success {{ background: #d4edda; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    .errors {{ background: #f8d7da; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    a {{ color: #007AFF; }}</style></head>
    <body><h1>Timetable Import Complete</h1>
    <div class="success">
        <p>Home rooms set: {results['home_rooms_set']}</p>
        <p>Timetable slots imported: {results['slots_imported']}</p>
    </div>
    {errors_html}
    <p><a href="/admin/">Back to Admin</a></p></body></html>
    '''


@admin_bp.route('/add-all-teachers')
def add_all_teachers():
    """Create user_sessions for all teachers in timetable_data."""
    from app.services.timetable_data import STAFF_HOME_ROOMS
    import uuid
    
    # Map magic_code to display name and surname for lookup
    TEACHER_INFO = {
        "athanathi": ("Ms Athanathi", "Maweni"),
        "muvo": ("Mr Muvo", "Hlongwana"),
        "smangaliso": ("Mr Smangaliso", "Mdluli"),
        "victor": ("Mr Victor", "Nyoni"),
        "alecia": ("Ms Alecia", "Green"),
        "anel": ("Ms Anel", "Meiring"),
        "anike": ("Ms Anike", "Conradie"),
        "beatrix": ("Ms Beatrix", "du Toit"),
        "bongi": ("Ms Bongi", "Mochabe"),
        "caelynne": ("Ms Caelynne", "Prinsloo"),
        "carina": ("Ms Carina", "Engelbrecht"),
        "carla": ("Ms Carla", "van der Walt"),
        "caroline": ("Ms Caroline", "Shiell"),
        "claire": ("Ms Claire", "Patrick"),
        "daleen": ("Ms Daleen", "Coetzee"),
        "dominique": ("Ms Dominique", "Viljoen"),
        "eugeni": ("Ms Eugeni", "Piek"),
        "jacqueline": ("Ms Jacqueline", "Sekhula"),
        "krisna": ("Ms Krisna", "Els"),
        "mamello": ("Ms Mamello", "Makgalemele"),
        "matti": ("Mr Matti", "van Wyk"),
        "nadia": ("Ms Nadia", "Stoltz"),
        "nathi": ("Mr Nathi", "Qwelane"),
        "nonhlanhla": ("Ms Nonhlanhla", "Maswanganyi"),
        "rianette": ("Ms Rianette", "van Vollenstee"),
        "rika": ("Ms Rika", "Badenhorst"),
        "robin": ("Ms Robin", "Harle"),
        "rochelle": ("Ms Rochelle", "Maass"),
        "rowena": ("Ms Rowena", "Kraamwinkel"),
        "teal": ("Ms Teal", "Mittendorf"),
        "thycha": ("Ms Thycha", "Aucamp"),
        "tsholofelo": ("Ms Tsholofelo", "Ramphomane"),
        "tyla": ("Ms Tyla", "Polayya"),
        "wendyann": ("Ms Wendyann", "van den Heever"),
        "zaudi": ("Ms Zaudi", "Pretorius"),
        "jean": ("Mr Jean", "Oosthuizen"),
        "ntando": ("Mr Ntando", "Mkunjulwa"),
        "kea": ("Ms Kea", "Mogapi"),
        "marielouise": ("Ms Marie-Louise", "Korb"),
        "mariska": ("Ms Mariska", "du Plessis"),
        "sinqobile": ("Ms Sinqobile", "Mchunu"),
    }
    
    results = {'created': [], 'existing': [], 'not_found': []}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for magic_code in STAFF_HOME_ROOMS.keys():
            # Check if session already exists
            cursor.execute("SELECT id FROM user_session WHERE magic_code = ? AND tenant_id = 'MARAGON'", (magic_code,))
            if cursor.fetchone():
                results['existing'].append(magic_code)
                continue
            
            # Get teacher info
            if magic_code not in TEACHER_INFO:
                results['not_found'].append(magic_code)
                continue
            
            display_name, surname = TEACHER_INFO[magic_code]
            
            # Find staff by surname
            cursor.execute("SELECT id FROM staff WHERE surname = ? AND tenant_id = 'MARAGON'", (surname,))
            staff = cursor.fetchone()
            
            if not staff:
                results['not_found'].append(f"{magic_code} (no staff: {surname})")
                continue
            
            # Create user_session
            cursor.execute("""
                INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
                VALUES (?, 'MARAGON', ?, ?, ?, 'teacher', 0)
            """, (str(uuid.uuid4()), staff['id'], magic_code, display_name))
            
            results['created'].append(magic_code)
        
        conn.commit()
    
    return f'''
    <html><head><title>Add All Teachers</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
    .success {{ background: #d4edda; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    .info {{ background: #cce5ff; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    .warning {{ background: #fff3cd; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
    a {{ color: #007AFF; }}</style></head>
    <body><h1>Add All Teachers</h1>
    <div class="success"><h3>Created: {len(results['created'])}</h3><p>{', '.join(results['created']) or 'None'}</p></div>
    <div class="info"><h3>Already existed: {len(results['existing'])}</h3><p>{', '.join(results['existing']) or 'None'}</p></div>
    <div class="warning"><h3>Not found: {len(results['not_found'])}</h3><p>{', '.join(results['not_found']) or 'None'}</p></div>
    <p><a href="/admin/import-timetable">Re-run Timetable Import</a></p>
    <p><a href="/admin/">Back to Admin</a></p></body></html>
    '''


@admin_bp.route('/add-jean')
def add_jean():
    """Add Jean Labuschagne user session."""
    import uuid
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Find Jean by surname Labuschagne (not Pierre)
        cursor.execute("SELECT id, display_name FROM staff WHERE surname = 'Labuschagne' AND first_name != 'Pierre' AND tenant_id = 'MARAGON'")
        staff = cursor.fetchone()
        
        if not staff:
            # Try adding the staff record
            staff_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO staff (id, tenant_id, title, first_name, surname, display_name, staff_type, can_substitute, is_active)
                VALUES (?, 'MARAGON', 'Mr', 'Jean', 'Labuschagne', 'Mr Jean', 'Teacher', 1, 1)
            """, (staff_id,))
        else:
            staff_id = staff['id']
        
        # Create user_session
        cursor.execute("DELETE FROM user_session WHERE magic_code = 'jean'")
        cursor.execute("""
            INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
            VALUES (?, 'MARAGON', ?, 'jean', 'Mr Jean', 'teacher', 0)
        """, (str(uuid.uuid4()), staff_id))
        
        conn.commit()
    
    return '<h1>Done</h1><p>Jean added. <a href="/admin/import-timetable">Re-run import</a></p>'


@admin_bp.route('/cycle-day-check')
def cycle_day_check():
    """Debug: Show cycle day calculations."""
    from datetime import date, timedelta
    from app.services.substitute_engine import get_cycle_day
    
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cycle_start_date, cycle_length FROM substitute_config WHERE tenant_id = 'MARAGON'")
        config = cursor.fetchone()
    
    return f'''
    <html><head><title>Cycle Day Check</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; }}</style></head>
    <body>
    <h1>Cycle Day Check</h1>
    <p><strong>Config start date:</strong> {config['cycle_start_date'] if config else 'Not set'}</p>
    <p><strong>Cycle length:</strong> {config['cycle_length'] if config else 'Not set'}</p>
    <hr>
    <p><strong>Today ({today.strftime('%a %d %b')}):</strong> Day {get_cycle_day(today)}</p>
    <p><strong>Tomorrow ({tomorrow.strftime('%a %d %b')}):</strong> Day {get_cycle_day(tomorrow)}</p>
    <p><a href="/admin/">Back</a></p>
    </body></html>
    '''


@admin_bp.route('/fix-cycle-start')
def fix_cycle_start():
    """Fix cycle start date to Jan 14."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE substitute_config 
            SET cycle_start_date = '2026-01-14' 
            WHERE tenant_id = 'MARAGON'
        """)
        conn.commit()
    return '<h1>Fixed!</h1><p>Cycle start date set to 2026-01-14</p><p><a href="/admin/cycle-day-check">Check cycle days</a></p>'


@admin_bp.route('/cycle-days-range')
def cycle_days_range():
    """Show cycle days for Jan 14-24."""
    from datetime import date, timedelta
    from app.services.substitute_engine import get_cycle_day
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cycle_start_date, cycle_length FROM substitute_config WHERE tenant_id = 'MARAGON'")
        config = cursor.fetchone()
    
    rows = ''
    start = date(2026, 1, 14)
    for i in range(10):
        d = start + timedelta(days=i)
        day_name = d.strftime('%a')
        if d.weekday() < 5:  # Weekday
            cycle = get_cycle_day(d)
            rows += f'<tr><td>{d.strftime("%d %b")}</td><td>{day_name}</td><td><strong>Day {cycle}</strong></td></tr>'
        else:
            rows += f'<tr style="color:#999"><td>{d.strftime("%d %b")}</td><td>{day_name}</td><td>Weekend</td></tr>'
    
    return f'''
    <html><head><title>Cycle Days</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; }}
    table {{ border-collapse: collapse; }} td, th {{ padding: 8px 16px; border: 1px solid #ddd; }}</style></head>
    <body>
    <h1>Cycle Days: Jan 14-23</h1>
    <p>Config start: {config['cycle_start_date'] if config else 'Not set'}</p>
    <table><tr><th>Date</th><th>Day</th><th>Cycle</th></tr>{rows}</table>
    <p><a href="/admin/fix-cycle-start">Fix to Jan 14</a> | <a href="/admin/">Back</a></p>
    </body></html>
    '''


@admin_bp.route('/fix-sub-eligibility')
def fix_sub_eligibility():
    """Set can_substitute=0 for non-teaching staff."""
    non_teachers = [
        'Tsewana',      # Andiswa - Lab Assistant
        'Munyai',       # Rebecca - Receptionist
        'Croeser',      # Annette - Bursar
        'Willemse',     # Janine - HR/PA
        'Letsoalo',     # Junior - STASY Admin
        'Ndimande',     # Njabulo - IT Support
        'Hibbard',      # Tamika - Ed Psychologist
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        fixed = []
        for surname in non_teachers:
            cursor.execute("""
                UPDATE staff SET can_substitute = 0 
                WHERE surname = ? AND tenant_id = 'MARAGON' AND can_substitute = 1
            """, (surname,))
            if cursor.rowcount > 0:
                fixed.append(surname)
        conn.commit()
    
    return f'<h1>Fixed</h1><p>Set can_substitute=0 for: {", ".join(fixed) or "None needed"}</p><p><a href="/admin/reset-substitute-test">Reset and retest</a></p>'


@admin_bp.route('/fix-all-sub-eligibility')
def fix_all_sub_eligibility():
    """Comprehensive fix for substitute eligibility."""
    
    # Cannot substitute - admin/management staff
    cannot_sub = [
        ('Hibbert', 'Delene'),      # Sports Manager
        ('Labuschagne', 'Pierre'),  # Principal
        ('Abrahams', 'Chelsea'),    # Teacher but no timetable yet
    ]
    
    results = {'fixed': [], 'not_found': []}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for surname, first_name in cannot_sub:
            cursor.execute("""
                UPDATE staff SET can_substitute = 0 
                WHERE surname = ? AND first_name = ? AND tenant_id = 'MARAGON'
            """, (surname, first_name))
            
            if cursor.rowcount > 0:
                results['fixed'].append(f"{first_name} {surname}")
            else:
                results['not_found'].append(f"{first_name} {surname}")
        
        conn.commit()
    
    return f'''
    <html><head><title>Fix Sub Eligibility</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; }}</style></head>
    <body>
    <h1>Substitute Eligibility Fixed</h1>
    <p><strong>Set can_substitute=0:</strong> {', '.join(results['fixed']) or 'None'}</p>
    <p><strong>Not found:</strong> {', '.join(results['not_found']) or 'None'}</p>
    <p><a href="/admin/reset-substitute-test">Reset and retest</a></p>
    </body></html>
    '''


@admin_bp.route('/fix-chelsea-left')
def fix_chelsea_left():
    """Chelsea Abrahams left - mark inactive. Jean Labuschagne replaced her."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Mark Chelsea as inactive
        cursor.execute("""
            UPDATE staff SET is_active = 0, can_substitute = 0 
            WHERE surname = 'Abrahams' AND first_name = 'Chelsea' AND tenant_id = 'MARAGON'
        """)
        chelsea_updated = cursor.rowcount
        
        # Ensure Jean can substitute
        cursor.execute("""
            UPDATE staff SET can_substitute = 1, is_active = 1
            WHERE surname = 'Labuschagne' AND first_name = 'Jean' AND tenant_id = 'MARAGON'
        """)
        jean_updated = cursor.rowcount
        
        conn.commit()
    
    return f'''<h1>Done</h1>
    <p>Chelsea Abrahams: is_active=0 (rows: {chelsea_updated})</p>
    <p>Jean Labuschagne: can_substitute=1 (rows: {jean_updated})</p>
    <p><a href="/admin/fix-all-sub-eligibility-v2">Run full eligibility fix</a></p>'''


@admin_bp.route('/fix-all-sub-eligibility-v2')
def fix_all_sub_eligibility_v2():
    """Comprehensive fix for ALL substitute eligibility issues."""
    
    cannot_sub = [
        ('Labuschagne', 'Pierre', 'Principal'),
        ('Mogapi', 'Kea', 'Deputy Principal'),
        ('Korb', 'Marie-Louise', 'Deputy Principal'),
        ('Hibbert', 'Delene', 'Sports Manager'),
        ('Croeser', 'Annette', 'Bursar'),
        ('Willemse', 'Janine', 'HR & PA'),
        ('Ndimande', 'Njabulo', 'IT Support'),
        ('Munyai', 'Rebecca', 'Receptionist'),
        ('Letsoalo', 'Junior', 'STASY Admin'),
        ('Hibbard', 'Tamika', 'Ed Psychologist'),
        ('Tsewana', 'Andiswa', 'Lab Assistant'),
    ]
    
    results = {'fixed': [], 'already': [], 'not_found': []}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for surname, first_name, reason in cannot_sub:
            cursor.execute("SELECT can_substitute FROM staff WHERE surname = ? AND first_name = ? AND tenant_id = 'MARAGON'", (surname, first_name))
            row = cursor.fetchone()
            
            if not row:
                results['not_found'].append(f"{first_name} {surname}")
            elif row['can_substitute'] == 0:
                results['already'].append(f"{first_name} {surname}")
            else:
                cursor.execute("UPDATE staff SET can_substitute = 0 WHERE surname = ? AND first_name = ? AND tenant_id = 'MARAGON'", (surname, first_name))
                results['fixed'].append(f"{first_name} {surname} ({reason})")
        
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) as cnt FROM staff WHERE tenant_id = 'MARAGON' AND is_active = 1 AND can_substitute = 1")
        can_sub_count = cursor.fetchone()['cnt']
    
    return f'''<html><head><title>Fix Eligibility</title>
    <style>body {{ font-family: -apple-system, sans-serif; padding: 2rem; }}</style></head>
    <body><h1>Substitute Eligibility Fixed</h1>
    <p><strong>Fixed now:</strong> {', '.join(results['fixed']) or 'None'}</p>
    <p><strong>Already correct:</strong> {', '.join(results['already']) or 'None'}</p>
    <p><strong>Not found:</strong> {', '.join(results['not_found']) or 'None'}</p>
    <hr><p><strong>Teachers who CAN substitute: {can_sub_count}</strong></p>
    <p><a href="/admin/reset-substitute-test">Reset and retest</a></p></body></html>'''


@admin_bp.route('/clear-safari-tokens')
def clear_safari_tokens():
    """Remove Safari push tokens that wake up Safari when emergencies are sent"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Find Safari tokens in push_token table (device_info contains user agent)
        cursor.execute("""
            SELECT id, device_info FROM push_token 
            WHERE device_info LIKE '%Safari%' AND device_info NOT LIKE '%Chrome%'
        """)
        safari_tokens = cursor.fetchall()
        
        # Delete them
        cursor.execute("""
            DELETE FROM push_token 
            WHERE device_info LIKE '%Safari%' AND device_info NOT LIKE '%Chrome%'
        """)
        deleted = cursor.rowcount
        conn.commit()
        
    return f"Found {len(safari_tokens)} Safari tokens. Deleted {deleted}."


@admin_bp.route('/fix-cycle-to-jan19')
def fix_cycle_to_jan19():
    """Fix cycle start date to Jan 19 (first real teaching day)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE substitute_config 
            SET cycle_start_date = '2026-01-19' 
            WHERE tenant_id = 'MARAGON'
        """)
        conn.commit()
    return '<h1>Fixed!</h1><p>Cycle start date set to 2026-01-19 (Day 1)</p><p>Mon 19 Jan = Day 1, Tue 20 Jan = Day 2, Wed 21 Jan = Day 3</p><p><a href="/admin/cycle-day-check">Check cycle days</a></p>'


@admin_bp.route('/reset-attendance-today')
def reset_attendance_today():
    """Clear all attendance records for today - demo reset."""
    from datetime import date
    today = date.today().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get attendance IDs for today
        cursor.execute("SELECT id FROM attendance WHERE attendance_date = ?", (today,))
        attendance_ids = [row['id'] for row in cursor.fetchall()]
        
        # Delete entries
        for att_id in attendance_ids:
            cursor.execute("DELETE FROM attendance_entry WHERE attendance_id = ?", (att_id,))
        
        # Delete attendance records
        cursor.execute("DELETE FROM attendance WHERE attendance_date = ?", (today,))
        deleted_count = cursor.rowcount
        
        # Clear pending marks
        cursor.execute("DELETE FROM pending_attendance")
        pending_count = cursor.rowcount
        
        conn.commit()
    
    return f'''<h1>Attendance Reset</h1>
<p>Cleared {deleted_count} attendance records for {today}</p>
<p>Cleared {pending_count} pending marks</p>
<p><a href="/admin/">Back to Admin</a></p>'''


@admin_bp.route('/fix-period-times')
def fix_period_times():
    """Update period table with correct Mon/Wed (type_a) times."""
    from app.services.db import get_connection
    
    # Mon/Wed times from bell schedule
    period_times = {
        1: ('08:20', '09:05'),
        2: ('09:05', '09:50'),
        3: ('10:10', '10:55'),
        4: ('10:55', '11:40'),
        5: ('11:40', '12:25'),
        6: ('12:45', '13:30'),
        7: ('13:30', '14:15'),
    }
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for period_num, (start, end) in period_times.items():
            cursor.execute("""
                UPDATE period 
                SET start_time = ?, end_time = ?
                WHERE tenant_id = 'MARAGON' AND period_number = ?
            """, (start, end, period_num))
        conn.commit()
    
    return f"<h2>Period Times Updated</h2><p>Updated {len(period_times)} periods to Mon/Wed times.</p><a href='/'>Home</a>"


@admin_bp.route('/dashboard-content')
def dashboard_content():
    """HTMX partial - returns just the stats and class list."""
    today = date.today()
    today_str = today.isoformat()
    
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
    
    return render_template('admin/partials/dashboard_content.html',
                          groups=groups,
                          total_groups=total_groups,
                          submitted_count=submitted_count,
                          pending_count=pending_count)


@admin_bp.route('/check-teacher-slots')
def check_teacher_slots():
    """Debug: Show what periods a teacher has in timetable_slot for a given day."""
    name = request.args.get('name', '')
    day = request.args.get('day', 1, type=int)
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ts.period_id, p.period_number, ts.subject, ts.class_name
            FROM timetable_slot ts
            JOIN period p ON ts.period_id = p.id
            JOIN staff s ON ts.staff_id = s.id
            WHERE LOWER(s.first_name) LIKE ? AND ts.cycle_day = ?
            ORDER BY p.period_number
        """, (f'%{name.lower()}%', day))
        slots = [dict(r) for r in cursor.fetchall()]
    
    return jsonify({'teacher': name, 'day': day, 'teaching_periods': slots})


@admin_bp.route('/check-sub-status')
def check_sub_status():
    """Check can_substitute status for specific teachers."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT first_name, surname, can_substitute 
            FROM staff 
            WHERE tenant_id = 'MARAGON' 
            AND LOWER(first_name) IN ('kea', 'marie-louise', 'pierre')
        """)
        results = [dict(r) for r in cursor.fetchall()]
    return jsonify(results)


@admin_bp.route('/declines')
def duty_declines():
    """View all duty declines (leadership only)."""
    from datetime import datetime
    
    staff_id = session.get('staff_id')
    role = session.get('role', '')
    
    # Leadership access check
    if not staff_id:
        return redirect('/')
    
    filter_type = request.args.get('type', '')
    
    TENANT_ID = "MARAGON"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if filter_type:
            cursor.execute("""
                SELECT * FROM duty_decline
                WHERE tenant_id = ? AND duty_type = ? AND reason != 'absent'
                ORDER BY declined_at DESC
                LIMIT 100
            """, (TENANT_ID, filter_type))
        else:
            cursor.execute("""
                SELECT * FROM duty_decline
                WHERE tenant_id = ? AND reason != 'absent'
                ORDER BY declined_at DESC
                LIMIT 100
            """, (TENANT_ID,))
        
        declines_raw = cursor.fetchall()
        declines = []
        
        for row in declines_raw:
            decline = dict(row)
            # Format duty date
            try:
                dt = datetime.strptime(decline['duty_date'], '%Y-%m-%d')
                decline['duty_date_display'] = dt.strftime('%a %d %b')
            except:
                decline['duty_date_display'] = decline['duty_date']
            
            # Format declined_at timestamp
            try:
                declined_dt = datetime.fromisoformat(decline['declined_at'].replace('Z', '+00:00'))
                decline['declined_at_display'] = declined_dt.strftime('%d %b at %H:%M')
            except:
                decline['declined_at_display'] = decline['declined_at']
            
            declines.append(decline)
    
    from app.services.nav import get_nav_header, get_nav_styles
    nav_header = get_nav_header("Duty Declines", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('admin/declines.html',
                          declines=declines,
                          filter_type=filter_type,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@admin_bp.route('/migrate/duty-decline')
def migrate_duty_decline():
    """One-time migration to create duty_decline table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duty_decline (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                duty_type TEXT NOT NULL,
                staff_id TEXT NOT NULL,
                staff_name TEXT NOT NULL,
                duty_description TEXT NOT NULL,
                duty_date DATE NOT NULL,
                reason TEXT,
                declined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_decline_tenant ON duty_decline(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_decline_date ON duty_decline(duty_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duty_decline_type ON duty_decline(duty_type)")
        conn.commit()
    return "duty_decline table created successfully"


@admin_bp.route('/add-junior-janine')
def add_junior_janine():
    """Add Junior (Office) and Janine (Management) user sessions."""
    import uuid
    
    results = {'added': [], 'errors': []}
    
    users_to_add = [
        {'surname': 'Letsoalo', 'first_name': 'Junior', 'magic_code': 'junior', 'role': 'teacher', 'display': 'Mr Junior'},
        {'surname': 'Willemse', 'first_name': 'Janine', 'magic_code': 'janine', 'role': 'deputy', 'display': 'Ms Janine'},
    ]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for user in users_to_add:
            cursor.execute(
                "SELECT id, display_name FROM staff WHERE surname = ? AND first_name = ? AND tenant_id = 'MARAGON'",
                (user['surname'], user['first_name'])
            )
            staff = cursor.fetchone()
            
            if not staff:
                results['errors'].append(f"{user['first_name']} {user['surname']} not found in staff")
                continue
            
            cursor.execute("SELECT id FROM user_session WHERE magic_code = ?", (user['magic_code'],))
            if cursor.fetchone():
                results['errors'].append(f"{user['magic_code']} already exists")
                continue
            
            cursor.execute("""
                INSERT INTO user_session (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
                VALUES (?, 'MARAGON', ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), staff['id'], user['magic_code'], user['display'], user['role'], 1 if user['role'] == 'deputy' else 0))
            
            results['added'].append({
                'name': user['display'],
                'role': user['role'],
                'link': f"https://schoolops.co.za/?u={user['magic_code']}"
            })
        
        conn.commit()
    
    return jsonify(results)
