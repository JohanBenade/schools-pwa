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


@admin_bp.route('/debug-substitute-seed')
def debug_substitute_seed():
    """Try seeding step by step."""
    import traceback
    
    results = {}
    
    # Step 1: Init tables
    try:
        from app.services.seed_substitute_data import init_substitute_tables
        init_substitute_tables()
        results['step1_init_tables'] = 'OK'
    except Exception as e:
        results['step1_init_tables'] = traceback.format_exc()
        return jsonify(results)
    
    # Step 2: Seed periods
    try:
        from app.services.seed_substitute_data import seed_periods
        count = seed_periods()
        results['step2_periods'] = f'OK - {count} periods'
    except Exception as e:
        results['step2_periods'] = traceback.format_exc()
        return jsonify(results)
    
    # Step 3: Seed config
    try:
        from app.services.seed_substitute_data import seed_substitute_config
        count = seed_substitute_config()
        results['step3_config'] = f'OK - {count}'
    except Exception as e:
        results['step3_config'] = traceback.format_exc()
        return jsonify(results)
    
    # Step 4: Seed timetable
    try:
        from app.services.seed_substitute_data import seed_demo_timetable
        count = seed_demo_timetable()
        results['step4_timetable'] = f'OK - {count} slots'
    except Exception as e:
        results['step4_timetable'] = traceback.format_exc()
        return jsonify(results)
    
    results['status'] = 'ALL COMPLETE'
    return jsonify(results)


@admin_bp.route('/verify-substitute-fixed')
def verify_substitute_fixed():
    """Verify substitute data is ready for demo."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Periods
        cursor.execute("""
            SELECT period_name, start_time, end_time 
            FROM period WHERE tenant_id = 'MARAGON' AND is_teaching = 1
            ORDER BY sort_order
        """)
        periods = [dict(row) for row in cursor.fetchall()]
        
        # Beatrix's schedule (sick teacher - B001)
        cursor.execute("""
            SELECT p.period_name, t.class_name, t.subject
            FROM timetable_slot t
            JOIN period p ON t.period_id = p.id
            JOIN staff s ON t.staff_id = s.id
            WHERE s.surname = 'du Toit' AND t.cycle_day = 3
            ORDER BY p.sort_order
        """)
        beatrix_schedule = [dict(row) for row in cursor.fetchall()]
        
        # Beatrix's classroom and mentor group
        cursor.execute("""
            SELECT s.id, s.display_name, v.venue_code, mg.group_name as mentor_class
            FROM staff s
            LEFT JOIN staff_venue sv ON s.id = sv.staff_id
            LEFT JOIN venue v ON sv.venue_id = v.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE s.surname = 'du Toit' AND s.tenant_id = 'MARAGON'
        """)
        row = cursor.fetchone()
        beatrix_info = dict(row) if row else None
        
        # Jacqueline's classroom (adjacent B002 - for roll call)
        cursor.execute("""
            SELECT s.id, s.display_name, v.venue_code, mg.group_name as mentor_class
            FROM staff s
            LEFT JOIN staff_venue sv ON s.id = sv.staff_id
            LEFT JOIN venue v ON sv.venue_id = v.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE s.surname = 'Sekhula' AND s.tenant_id = 'MARAGON'
        """)
        row = cursor.fetchone()
        jacqueline_info = dict(row) if row else None
        
        # Config
        cursor.execute("SELECT * FROM substitute_config WHERE tenant_id = 'MARAGON'")
        row = cursor.fetchone()
        config = dict(row) if row else None
        
        # Check adjacency
        beatrix_room = beatrix_info.get('venue_code') if beatrix_info else None
        jacqueline_room = jacqueline_info.get('venue_code') if jacqueline_info else None
        is_adjacent = False
        if beatrix_room and jacqueline_room:
            # B001 and B002 are adjacent
            is_adjacent = (beatrix_room[:1] == jacqueline_room[:1] and 
                          abs(int(beatrix_room[1:]) - int(jacqueline_room[1:])) <= 2)
        
    return jsonify({
        'periods': periods,
        'sick_teacher': {
            'info': beatrix_info,
            'day3_schedule': beatrix_schedule,
            'periods_to_cover': len(beatrix_schedule)
        },
        'roll_call_cover': {
            'info': jacqueline_info,
            'is_adjacent_to_beatrix': is_adjacent,
            'note': 'Roll call is before school - no timetable check needed, just proximity'
        },
        'config': config,
        'demo_ready': len(beatrix_schedule) == 5 and is_adjacent
    })


@admin_bp.route('/setup-substitute-demo')
def setup_substitute_demo():
    """Ensure demo users exist for substitute testing."""
    from datetime import datetime
    import uuid
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get Beatrix's staff ID
        cursor.execute("""
            SELECT id, display_name FROM staff 
            WHERE surname = 'du Toit' AND tenant_id = 'MARAGON'
        """)
        beatrix = cursor.fetchone()
        
        results = {'beatrix': None, 'sessions_created': []}
        
        if beatrix:
            results['beatrix'] = dict(beatrix)
            
            # Check if session exists
            cursor.execute("""
                SELECT * FROM user_session WHERE magic_code = 'beatrix'
            """)
            existing = cursor.fetchone()
            
            if not existing:
                # Create session for Beatrix
                cursor.execute("""
                    INSERT INTO user_session 
                    (id, tenant_id, staff_id, magic_code, display_name, role, can_resolve)
                    VALUES (?, 'MARAGON', ?, 'beatrix', ?, 'teacher', 0)
                """, (str(uuid.uuid4()), beatrix['id'], beatrix['display_name']))
                results['sessions_created'].append('beatrix')
        
        # Ensure Pierre has principal role (might already exist)
        cursor.execute("""
            UPDATE user_session SET role = 'principal', can_resolve = 1 
            WHERE magic_code = 'pierre'
        """)
        
        # Ensure admin has admin role
        cursor.execute("""
            UPDATE user_session SET role = 'admin', can_resolve = 1 
            WHERE magic_code = 'admin'
        """)
        
        conn.commit()
        
        # List all sessions
        cursor.execute("""
            SELECT magic_code, display_name, role FROM user_session 
            WHERE tenant_id = 'MARAGON'
        """)
        results['all_sessions'] = [dict(row) for row in cursor.fetchall()]
        
    return jsonify(results)


@admin_bp.route('/debug-substitute-pages')
def debug_substitute_pages():
    """Debug substitute page errors."""
    import traceback
    from flask import session
    
    results = {}
    
    # Test 1: Check session
    results['session'] = {
        'staff_id': session.get('staff_id'),
        'display_name': session.get('display_name'),
        'role': session.get('role')
    }
    
    # Test 2: Try importing substitute blueprint
    try:
        from app.routes.substitute import substitute_bp
        results['import_blueprint'] = 'OK'
    except Exception as e:
        results['import_blueprint'] = traceback.format_exc()
        return jsonify(results)
    
    # Test 3: Try importing engine
    try:
        from app.services.substitute_engine import get_cycle_day, get_current_pointer
        results['import_engine'] = 'OK'
        results['cycle_day'] = get_cycle_day()
        results['pointer'] = get_current_pointer()
    except Exception as e:
        results['import_engine'] = traceback.format_exc()
        return jsonify(results)
    
    # Test 4: Check templates exist
    import os
    template_dir = 'app/templates/substitute'
    if os.path.exists(template_dir):
        results['templates'] = os.listdir(template_dir)
    else:
        results['templates'] = 'DIRECTORY NOT FOUND'
    
    # Test 5: Try a simple query
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM period WHERE tenant_id = 'MARAGON'")
            results['period_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM timetable_slot WHERE tenant_id = 'MARAGON'")
            results['timetable_count'] = cursor.fetchone()[0]
    except Exception as e:
        results['db_query'] = traceback.format_exc()
    
    return jsonify(results)


@admin_bp.route('/debug-substitute-render')
def debug_substitute_render():
    """Test rendering each substitute page."""
    import traceback
    from flask import session
    
    results = {}
    
    # Set a test session if needed
    if 'staff_id' not in session:
        results['warning'] = 'No session - some tests may fail'
    
    # Test 1: Index page
    try:
        from app.routes.substitute import substitute_bp
        from flask import render_template
        html = render_template('substitute/index.html',
                              staff_id=session.get('staff_id'),
                              display_name=session.get('display_name', 'Test'))
        results['index'] = f'OK - {len(html)} chars'
    except Exception as e:
        results['index'] = traceback.format_exc()
    
    # Test 2: Report page
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, period_number, period_name, start_time, end_time
                FROM period 
                WHERE tenant_id = 'MARAGON' AND is_teaching = 1
                ORDER BY sort_order
            """)
            periods = [dict(row) for row in cursor.fetchall()]
        
        from datetime import date
        html = render_template('substitute/report.html',
                              periods=periods,
                              today=date.today().isoformat())
        results['report'] = f'OK - {len(html)} chars'
    except Exception as e:
        results['report'] = traceback.format_exc()
    
    # Test 3: My assignments page
    try:
        from app.services.substitute_engine import get_cycle_day
        html = render_template('substitute/my_assignments.html',
                              schedule=[],
                              mentor_duty=None,
                              today=date.today().isoformat(),
                              cycle_day=get_cycle_day(),
                              sub_count=0)
        results['my_assignments'] = f'OK - {len(html)} chars'
    except Exception as e:
        results['my_assignments'] = traceback.format_exc()
    
    # Test 4: Mission control
    try:
        html = render_template('substitute/mission_control.html',
                              absences=[],
                              config={'pointer_surname': 'A'},
                              cycle_day=3,
                              today='2026-01-10',
                              stats={'total': 0, 'covered': 0, 'partial': 0, 'escalated': 0})
        results['mission_control'] = f'OK - {len(html)} chars'
    except Exception as e:
        results['mission_control'] = traceback.format_exc()
    
    return jsonify(results)


@admin_bp.route('/fix-substitute-table')
def fix_substitute_table():
    """Add missing columns to substitute_request table."""
    import traceback
    
    results = {'fixes_applied': []}
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Check current columns
            cursor.execute("PRAGMA table_info(substitute_request)")
            existing_cols = {row['name'] for row in cursor.fetchall()}
            results['existing_columns'] = list(existing_cols)
            
            # Add missing columns one by one
            columns_to_add = [
                ('is_mentor_duty', 'INTEGER DEFAULT 0'),
                ('mentor_group_id', 'TEXT'),
                ('subject', 'TEXT'),
                ('class_name', 'TEXT'),
                ('venue_name', 'TEXT'),
                ('declined_at', 'TEXT'),
                ('declined_by_id', 'TEXT'),
                ('decline_reason', 'TEXT'),
                ('push_sent_at', 'TEXT'),
                ('push_queued_until', 'TEXT'),
                ('original_substitute_id', 'TEXT'),
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in existing_cols:
                    try:
                        cursor.execute(f"ALTER TABLE substitute_request ADD COLUMN {col_name} {col_type}")
                        results['fixes_applied'].append(f"Added {col_name}")
                    except Exception as e:
                        results['fixes_applied'].append(f"Failed {col_name}: {str(e)}")
            
            conn.commit()
            
            # Verify
            cursor.execute("PRAGMA table_info(substitute_request)")
            results['final_columns'] = [row['name'] for row in cursor.fetchall()]
            
    except Exception as e:
        results['error'] = traceback.format_exc()
    
    return jsonify(results)


@admin_bp.route('/fix-timetable-all-days')
def fix_timetable_all_days():
    """Copy Day 3 timetable to all cycle days (1-7) so demo works any day."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get all Day 3 slots
        cursor.execute("""
            SELECT staff_id, period_id, class_name, subject, venue_id
            FROM timetable_slot
            WHERE tenant_id = 'MARAGON' AND cycle_day = 3
        """)
        day3_slots = cursor.fetchall()
        
        if not day3_slots:
            return jsonify({'error': 'No Day 3 slots found'})
        
        # Delete existing slots for other days
        cursor.execute("""
            DELETE FROM timetable_slot 
            WHERE tenant_id = 'MARAGON' AND cycle_day != 3
        """)
        
        # Copy Day 3 to Days 1, 2, 4, 5, 6, 7
        import uuid
        count = 0
        for day in [1, 2, 4, 5, 6, 7]:
            for slot in day3_slots:
                cursor.execute("""
                    INSERT INTO timetable_slot 
                    (id, tenant_id, staff_id, cycle_day, period_id, class_name, subject, venue_id)
                    VALUES (?, 'MARAGON', ?, ?, ?, ?, ?, ?)
                """, (str(uuid.uuid4()), slot['staff_id'], day, slot['period_id'], 
                      slot['class_name'], slot['subject'], slot['venue_id']))
                count += 1
        
        conn.commit()
        
        # Verify
        cursor.execute("""
            SELECT cycle_day, COUNT(*) as slots
            FROM timetable_slot WHERE tenant_id = 'MARAGON'
            GROUP BY cycle_day ORDER BY cycle_day
        """)
        by_day = [dict(row) for row in cursor.fetchall()]
        
    return jsonify({
        'day3_slots_copied': len(day3_slots),
        'new_slots_created': count,
        'slots_by_day': by_day
    })


@admin_bp.route('/fix-substitute-request-nullable')
def fix_substitute_request_nullable():
    """Fix substitute_request table to allow NULL period_id for mentor duties."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
        # First, backup existing data
        cursor.execute("SELECT * FROM substitute_request")
        existing = cursor.fetchall()
        
        # Drop and recreate with nullable period_id
        cursor.execute("DROP TABLE IF EXISTS substitute_request_backup")
        cursor.execute("ALTER TABLE substitute_request RENAME TO substitute_request_backup")
        
        cursor.execute("""
            CREATE TABLE substitute_request (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                absence_id TEXT NOT NULL,
                period_id TEXT,
                class_group_id TEXT,
                venue_id TEXT,
                substitute_id TEXT,
                status TEXT DEFAULT 'Pending',
                assigned_at TEXT,
                confirmed_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT,
                is_mentor_duty INTEGER DEFAULT 0,
                mentor_group_id TEXT,
                subject TEXT,
                class_name TEXT,
                venue_name TEXT,
                declined_at TEXT,
                declined_by_id TEXT,
                decline_reason TEXT,
                push_sent_at TEXT,
                push_queued_until TEXT,
                original_substitute_id TEXT,
                FOREIGN KEY (absence_id) REFERENCES absence(id)
            )
        """)
        
        # Restore data
        for row in existing:
            cursor.execute("""
                INSERT INTO substitute_request 
                (id, tenant_id, absence_id, period_id, class_group_id, venue_id, 
                 substitute_id, status, assigned_at, confirmed_at, created_at, updated_at,
                 is_mentor_duty, mentor_group_id, subject, class_name, venue_name,
                 declined_at, declined_by_id, decline_reason, push_sent_at, 
                 push_queued_until, original_substitute_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['id'], row['tenant_id'], row['absence_id'], row['period_id'],
                row['class_group_id'], row['venue_id'], row['substitute_id'],
                row['status'], row['assigned_at'], row['confirmed_at'],
                row['created_at'], row['updated_at'], row['is_mentor_duty'],
                row['mentor_group_id'], row['subject'], row['class_name'],
                row['venue_name'], row['declined_at'], row['declined_by_id'],
                row['decline_reason'], row['push_sent_at'], row['push_queued_until'],
                row['original_substitute_id']
            ))
        
        # Drop backup
        cursor.execute("DROP TABLE substitute_request_backup")
        
        conn.commit()
        
        # Verify
        cursor.execute("PRAGMA table_info(substitute_request)")
        cols = [{'name': row['name'], 'notnull': row['notnull']} for row in cursor.fetchall()]
        
    return jsonify({
        'success': True,
        'rows_migrated': len(existing),
        'columns': cols
    })


@admin_bp.route('/fix-substitute-roles')
def fix_substitute_roles():
    """Set can_substitute=0 for principals, deputies, and admin staff."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # First check if can_substitute column exists
        cursor.execute("PRAGMA table_info(staff)")
        columns = [row['name'] for row in cursor.fetchall()]
        
        if 'can_substitute' not in columns:
            cursor.execute("ALTER TABLE staff ADD COLUMN can_substitute INTEGER DEFAULT 1")
            conn.commit()
        
        # Set everyone to can_substitute = 1 first
        cursor.execute("UPDATE staff SET can_substitute = 1 WHERE tenant_id = 'MARAGON'")
        
        # Get staff IDs for non-teachers (principal, deputy, admin roles)
        cursor.execute("""
            SELECT s.id, s.display_name, us.role 
            FROM staff s
            JOIN user_session us ON s.id = us.staff_id
            WHERE us.role IN ('principal', 'deputy', 'admin')
            AND us.tenant_id = 'MARAGON'
        """)
        non_teachers = cursor.fetchall()
        
        excluded = []
        for row in non_teachers:
            cursor.execute("UPDATE staff SET can_substitute = 0 WHERE id = ?", (row['id'],))
            excluded.append({'name': row['display_name'], 'role': row['role']})
        
        conn.commit()
        
        # Verify
        cursor.execute("""
            SELECT display_name, can_substitute 
            FROM staff 
            WHERE tenant_id = 'MARAGON' 
            ORDER BY can_substitute, display_name
        """)
        all_staff = [dict(row) for row in cursor.fetchall()]
        
    return jsonify({
        'excluded_from_substituting': excluded,
        'staff_status': all_staff[:15],
        'note': 'Showing first 15 staff members'
    })


@admin_bp.route('/reset-substitute-test')
def reset_substitute_test():
    """Clear substitute data and reset pointer for fresh testing."""
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Clear existing substitute data
        cursor.execute("DELETE FROM substitute_request WHERE tenant_id = 'MARAGON'")
        cursor.execute("DELETE FROM absence WHERE tenant_id = 'MARAGON'")
        cursor.execute("DELETE FROM substitute_log WHERE tenant_id = 'MARAGON'")
        
        # Reset pointer to 'A'
        cursor.execute("""
            UPDATE substitute_config 
            SET pointer_surname = 'A', pointer_updated_at = datetime('now')
            WHERE tenant_id = 'MARAGON'
        """)
        
        conn.commit()
        
    return jsonify({
        'success': True,
        'message': 'Substitute test data cleared, pointer reset to A'
    })
