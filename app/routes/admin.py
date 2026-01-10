"""
Admin routes - Attendance dashboard for office admin
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from datetime import date, datetime
from app.services.db import get_connection

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

TENANT_ID = "MARAGON"


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
        
        # Sort: Submitted (needs action) -> Pending -> Done (all present OR fully captured)
        def sort_key(g):
            absent = g['absent_count'] or 0
            captured = g['captured_count'] or 0
            is_fully_captured = g['attendance_id'] and absent > 0 and captured == absent
            is_all_present = g['attendance_id'] and absent == 0
            is_done = is_fully_captured or is_all_present
            is_submitted_needs_action = g['attendance_id'] and absent > 0 and captured < absent
            is_pending = not g['attendance_id']
            
            # Sort order: 0=submitted needs action, 1=pending, 2=done
            if is_submitted_needs_action:
                priority = 0
            elif is_pending:
                priority = 1
            else:  # done (all present or fully captured)
                priority = 2
            
            return (priority, g['group_name'])
        
        groups = sorted(groups, key=sort_key)
    
    return render_template('admin/dashboard.html',
                          today_display=today_display,
                          groups=groups,
                          total_groups=total_groups,
                          submitted_count=submitted_count,
                          pending_count=pending_count,
                          total_present=total_present,
                          total_absent=total_absent,
                          total_captured=total_captured,
                          total_late=total_late)


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
    
    return render_template('admin/absentees.html',
                          today_display=today_display,
                          absentees=absentees,
                          total=total,
                          captured=captured)


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
    
    return render_template('admin/late.html',
                          today_display=today_display,
                          late_learners=late)


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
        
        # Format date for display
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
    
    return render_template('admin/class_detail.html',
                          attendance=attendance,
                          entries=entries)


@admin_bp.route('/override/<entry_id>', methods=['POST'])
def override_status(entry_id):
    """Admin override of learner status."""
    new_status = request.form.get('status')
    attendance_id = request.form.get('attendance_id')
    return_to = request.form.get('return_to', 'class')
    
    if new_status in ('Present', 'Absent', 'Late'):
        with get_connection() as conn:
            cursor = conn.cursor()
            # If changing FROM Absent, clear stasy_captured
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
# SEED DATA ENDPOINT
# ============================================

@admin_bp.route('/seed-data', methods=['GET', 'POST'])
def seed_data():
    """Seed Maragon reference data. GET shows confirmation, POST executes."""
    if request.method == 'GET':
        # Show current counts and confirmation
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM staff")
            staff_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM mentor_group")
            mg_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM learner")
            learner_count = cursor.fetchone()[0]
        
        return f'''
        <html>
        <head><title>Seed Data - SchoolOps Admin</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
            .warning {{ background: #fee; border: 1px solid #c00; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            .current {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            button {{ background: #c00; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; }}
            button:hover {{ background: #a00; }}
            a {{ color: #007AFF; }}
        </style>
        </head>
        <body>
            <h1>Seed Maragon Data</h1>
            <div class="current">
                <h3>Current Data</h3>
                <p>Staff: {staff_count}</p>
                <p>Mentor Groups: {mg_count}</p>
                <p>Learners: {learner_count}</p>
            </div>
            <div class="warning">
                <h3>Warning</h3>
                <p>This will DELETE all existing data and replace with fresh Maragon seed data:</p>
                <ul>
                    <li>54 staff members</li>
                    <li>25 mentor groups</li>
                    <li>125 test learners</li>
                </ul>
                <p><strong>All attendance records will be lost!</strong></p>
            </div>
            <form method="POST">
                <button type="submit">Seed Data Now</button>
            </form>
            <p style="margin-top: 2rem;"><a href="/admin/">Back to Dashboard</a></p>
        </body>
        </html>
        '''
    
    # POST - Execute seed
    from app.services.seed_maragon_data import seed_all
    result = seed_all()
    
    return f'''
    <html>
    <head><title>Seed Complete - SchoolOps Admin</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
        .success {{ background: #efe; border: 1px solid #0a0; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        a {{ color: #007AFF; }}
    </style>
    </head>
    <body>
        <h1>Seed Complete</h1>
        <div class="success">
            <h3>Data Imported</h3>
            <p>Staff: {result['staff']}</p>
            <p>Mentor Groups: {result['mentor_groups']}</p>
            <p>Learners: {result['learners']}</p>
        </div>
        <p><a href="/admin/">Go to Dashboard</a></p>
        <p><a href="/attendance/">Go to Attendance</a></p>
    </body>
    </html>
    '''


@admin_bp.route('/db-stats')
def db_stats():
    """Show database statistics (no modification)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        stats = {}
        for table in ['staff', 'mentor_group', 'learner', 'grade', 'attendance', 'attendance_entry']:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
    
    return jsonify(stats)


@admin_bp.route('/seed-emergency', methods=['GET', 'POST'])
def seed_emergency():
    """Seed emergency-related data: venues, staff-venues, user sessions."""
    if request.method == 'GET':
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM venue WHERE tenant_id = 'MARAGON'")
            venue_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM user_session WHERE tenant_id = 'MARAGON'")
            session_count = cursor.fetchone()[0]
            
            # Check if push_token table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='push_token'")
            push_table_exists = cursor.fetchone() is not None
        
        return f'''
        <html>
        <head><title>Seed Emergency Data - SchoolOps Admin</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
            .info {{ background: #e0f2fe; border: 1px solid #0284c7; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            .current {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            button {{ background: #3b82f6; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; }}
            button:hover {{ background: #2563eb; }}
            a {{ color: #007AFF; }}
            .magic-links {{ background: #f0fdf4; border: 1px solid #22c55e; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            .magic-links code {{ background: #dcfce7; padding: 2px 6px; border-radius: 4px; }}
        </style>
        </head>
        <body>
            <h1>Seed Emergency Data</h1>
            <div class="current">
                <h3>Current Data</h3>
                <p>Venues: {venue_count}</p>
                <p>User Sessions: {session_count}</p>
                <p>Push Token Table: {'✅ Exists' if push_table_exists else '❌ Missing (will be created)'}</p>
            </div>
            <div class="info">
                <h3>This will create:</h3>
                <ul>
                    <li>~55 venues (classrooms, offices, terrain areas)</li>
                    <li>Staff-to-venue assignments</li>
                    <li>Magic link user sessions for demo</li>
                    <li>Push notification token table (if missing)</li>
                </ul>
            </div>
            <form method="POST">
                <button type="submit">Seed Emergency Data</button>
            </form>
            <p style="margin-top: 2rem;"><a href="/admin/">Back to Dashboard</a></p>
        </body>
        </html>
        '''
    
    # POST - Execute seed
    # First ensure push_token table exists
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_token (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                staff_id TEXT,
                token TEXT NOT NULL UNIQUE,
                device_info TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_used_at TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_tenant ON push_token(tenant_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_staff ON push_token(staff_id)')
        conn.commit()
    
    from app.services.seed_emergency_data import seed_all_emergency
    result = seed_all_emergency()
    
    return f'''
    <html>
    <head><title>Seed Complete - SchoolOps Admin</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
        .success {{ background: #dcfce7; border: 1px solid #22c55e; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        a {{ color: #007AFF; }}
        .magic-links {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        .magic-links h3 {{ margin-top: 0; }}
        .link {{ display: block; margin: 8px 0; padding: 8px; background: white; border-radius: 4px; word-break: break-all; }}
    </style>
    </head>
    <body>
        <h1>Emergency Data Seeded</h1>
        <div class="success">
            <h3>Data Created</h3>
            <p>Venues: {result['venues']}</p>
            <p>Staff-Venue Assignments: {result['staff_venues']}</p>
            <p>User Sessions: {result['user_sessions']}</p>
            <p>Push Token Table: ✅ Ready</p>
        </div>
        
        <div class="magic-links">
            <h3>Magic Links for Demo</h3>
            <p>Send these via WhatsApp:</p>
            <div class="link"><strong>Nadia:</strong> https://schoolops.co.za/?u=nadia</div>
            <div class="link"><strong>Principal:</strong> https://schoolops.co.za/?u=pierre</div>
            <div class="link"><strong>Admin:</strong> https://schoolops.co.za/?u=admin</div>
        </div>
        
        <p><a href="/">Go to Home</a></p>
        <p><a href="/emergency/">Test Emergency</a></p>
    </body>
    </html>
    '''


@admin_bp.route('/init-push')
def init_push():
    """Create push_token table if it doesn't exist. Safe to run multiple times."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS push_token (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                staff_id TEXT,
                token TEXT NOT NULL UNIQUE,
                device_info TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_used_at TEXT
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_tenant ON push_token(tenant_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_push_token_staff ON push_token(staff_id)')
        conn.commit()
        
        cursor.execute("SELECT COUNT(*) FROM push_token")
        token_count = cursor.fetchone()[0]
    
    return jsonify({
        'success': True,
        'message': 'push_token table ready',
        'registered_tokens': token_count
    })


@admin_bp.route('/seed-substitute', methods=['GET', 'POST'])
def seed_substitute():
    """Seed substitute allocation data: periods, config, demo timetable."""
    if request.method == 'GET':
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM period WHERE tenant_id = 'MARAGON'")
            period_count = cursor.fetchone()[0]
            
            # Check if timetable_slot table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='timetable_slot'")
            timetable_exists = cursor.fetchone() is not None
            
            slot_count = 0
            if timetable_exists:
                cursor.execute("SELECT COUNT(*) FROM timetable_slot WHERE tenant_id = 'MARAGON'")
                slot_count = cursor.fetchone()[0]
        
        return f'''
        <html>
        <head><title>Seed Substitute Data - SchoolOps Admin</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
            .info {{ background: #fef3c7; border: 1px solid #f59e0b; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            .current {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
            button {{ background: #f97316; color: white; border: none; padding: 1rem 2rem; border-radius: 8px; font-size: 1rem; cursor: pointer; }}
            button:hover {{ background: #ea580c; }}
            a {{ color: #007AFF; }}
        </style>
        </head>
        <body>
            <h1>🔄 Seed Substitute Data</h1>
            <div class="current">
                <h3>Current Data</h3>
                <p>Periods: {period_count}</p>
                <p>Timetable Slots: {slot_count}</p>
            </div>
            <div class="info">
                <h3>This will create:</h3>
                <ul>
                    <li>9 periods (7 teaching + 2 breaks)</li>
                    <li>Substitute config (A-Z pointer, quiet hours)</li>
                    <li>Demo timetable for Day 3:</li>
                    <ul>
                        <li>Ms Beatrix: 5 teaching periods (demo sick teacher)</li>
                        <li>Ms Jacqueline: Adjacent classroom B002 (roll call)</li>
                        <li>All other teachers: ~70% load</li>
                    </ul>
                </ul>
            </div>
            <form method="POST">
                <button type="submit">Seed Substitute Data</button>
            </form>
            <p style="margin-top: 2rem;"><a href="/admin/">Back to Dashboard</a></p>
        </body>
        </html>
        '''
    
    # POST - Execute seed
    from app.services.seed_substitute_data import seed_all_substitute
    result = seed_all_substitute()
    
    return f'''
    <html>
    <head><title>Seed Complete - SchoolOps Admin</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; padding: 2rem; max-width: 600px; margin: 0 auto; }}
        .success {{ background: #dcfce7; border: 1px solid #22c55e; padding: 1rem; border-radius: 8px; margin: 1rem 0; }}
        a {{ color: #007AFF; }}
    </style>
    </head>
    <body>
        <h1>✅ Substitute Data Seeded</h1>
        <div class="success">
            <h3>Data Created</h3>
            <p>Periods: {result['periods']}</p>
            <p>Config: {result['config']}</p>
            <p>Timetable Slots: {result['timetable_slots']}</p>
        </div>
        <p><a href="/admin/">Back to Dashboard</a></p>
    </body>
    </html>
    '''


@admin_bp.route('/debug-substitute')
def debug_substitute():
    """Debug substitute setup."""
    import traceback
    
    results = {}
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Check staff table
            cursor.execute("SELECT COUNT(*) FROM staff WHERE tenant_id = 'MARAGON'")
            results['staff_count'] = cursor.fetchone()[0]
            
            # Check for Beatrix
            cursor.execute("SELECT id, surname FROM staff WHERE surname LIKE '%Toit%' AND tenant_id = 'MARAGON'")
            row = cursor.fetchone()
            results['beatrix'] = dict(row) if row else 'NOT FOUND'
            
            # Check venues
            cursor.execute("SELECT COUNT(*) FROM venue WHERE tenant_id = 'MARAGON'")
            results['venue_count'] = cursor.fetchone()[0]
            
            # Check B001
            cursor.execute("SELECT id, venue_code FROM venue WHERE venue_code = 'B001' AND tenant_id = 'MARAGON'")
            row = cursor.fetchone()
            results['b001'] = dict(row) if row else 'NOT FOUND'
            
            # Try importing the seed module
            try:
                from app.services.seed_substitute_data import init_substitute_tables
                results['import'] = 'OK'
            except Exception as e:
                results['import'] = str(e)
            
    except Exception as e:
        results['error'] = str(e)
        results['traceback'] = traceback.format_exc()
    
    return jsonify(results)
