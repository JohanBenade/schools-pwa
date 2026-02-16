"""
SchoolOps Flask Application
"""
from flask import Flask, session, request, redirect, render_template
from dotenv import load_dotenv
import os

load_dotenv()

# Run pending database migrations
try:
    from app.services.migrations import run_on_startup
    run_on_startup()
except Exception as e:
    print(f"Migration startup: {e}")

TENANT_ID = "MARAGON"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    from datetime import timedelta
    app.permanent_session_lifetime = timedelta(days=365)
    
    from app.routes.attendance import attendance_bp
    from app.routes.admin import admin_bp
    from app.routes.principal import principal_bp
    from app.routes.emergency import emergency_bp
    from app.routes.push import push_bp
    from app.routes.substitute import substitute_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.duty import duty_bp
    from app.routes.sport import sport_bp
    from app.routes.absences import absences_bp
    from app.routes.timetables import timetables_bp
    from app.routes.terrain_admin import terrain_admin_bp
    
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(principal_bp)
    app.register_blueprint(emergency_bp)
    app.register_blueprint(push_bp)
    app.register_blueprint(substitute_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(duty_bp)
    app.register_blueprint(sport_bp)
    app.register_blueprint(absences_bp)
    app.register_blueprint(timetables_bp)
    app.register_blueprint(terrain_admin_bp)
    
    @app.before_request
    def check_password_gate():
        session.permanent = True
        if request.path.startswith('/static') or request.path in ['/gate', '/login-code']:
            return
        if session.get('gate_passed'):
            return
        if request.method == 'POST' and request.path == '/gate':
            return
        magic_code = request.args.get('u')
        if magic_code:
            return redirect(f'/gate?u={magic_code}')
        return redirect('/gate')
    
    @app.route('/gate', methods=['GET', 'POST'])
    def password_gate():
        error = None
        magic_code = request.args.get('u', '') or request.form.get('u', '')
        if request.method == 'POST':
            password = request.form.get('password', '')
            if password == 'maragon2026':
                session['gate_passed'] = True
                if magic_code:
                    return redirect(f'/?u={magic_code}')
                return redirect('/')
            else:
                error = 'Incorrect password'
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SchoolOps</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .gate-box {{ background: rgba(255,255,255,0.1); padding: 40px; border-radius: 16px; text-align: center; max-width: 320px; width: 100%; }}
        h1 {{ color: white; font-size: 24px; margin-bottom: 8px; }}
        p {{ color: rgba(255,255,255,0.7); font-size: 14px; margin-bottom: 24px; }}
        input {{ width: 100%; padding: 14px 16px; border: none; border-radius: 8px; font-size: 16px; margin-bottom: 16px; text-align: center; }}
        button {{ width: 100%; padding: 14px; background: #3b82f6; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }}
        button:active {{ background: #2563eb; }}
        .error {{ color: #f87171; font-size: 14px; margin-bottom: 16px; }}
    </style>
</head>
<body>
    <div class="gate-box">
        <h1>SchoolOps</h1>
        <p>Pilot access only</p>
        {"<div class='error'>" + error + "</div>" if error else ""}
        <form method="POST">
            {'<input type="hidden" name="u" value="' + magic_code + '">' if magic_code else ''}
            <input type="password" name="password" placeholder="Enter password" autofocus>
            <button type="submit">Enter</button>
        </form>
    </div>
</body>
</html>
'''

    @app.before_request
    def handle_magic_link():
        magic_code = request.args.get('u')
        if magic_code:
            from app.services.db import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT us.*, sv.venue_id as default_venue_id, v.venue_name as default_venue_name
                    FROM user_session us
                    LEFT JOIN staff_venue sv ON us.staff_id = sv.staff_id
                    LEFT JOIN venue v ON sv.venue_id = v.id
                    WHERE us.magic_code = ? AND us.tenant_id = ?
                """, (magic_code.lower(), TENANT_ID))
                row = cursor.fetchone()
                if row:
                    session['staff_id'] = row['staff_id']
                    session['display_name'] = row['display_name']
                    session['role'] = row['role']
                    session['can_resolve'] = bool(row['can_resolve'])
                    session['default_venue_id'] = row['default_venue_id']
                    session['default_venue_name'] = row['default_venue_name']
                    session['tenant_id'] = TENANT_ID
            return redirect(request.path)
    
    @app.context_processor
    def inject_user():
        return {
            'current_user': {
                'staff_id': session.get('staff_id'),
                'display_name': session.get('display_name'),
                'role': session.get('role'),
                'can_resolve': session.get('can_resolve', False),
            }
        }
    
    @app.route('/')
    def home():
        from app.services.db import get_connection
        
        # Check for active emergency alert
        active_alert = None
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, alert_type, location_display FROM emergency_alert WHERE tenant_id = ? AND status = 'Active' ORDER BY triggered_at DESC LIMIT 1", (TENANT_ID,))
            row = cursor.fetchone()
            if row:
                active_alert = dict(row)
        
        user_name = session.get('display_name', '')
        user_logged_in = 'staff_id' in session
        user_role = session.get('role', '')
        
        # Route to appropriate home page based on role
        if user_role in ['principal', 'deputy']:
            return render_template('home/management.html', user_name=user_name, active_alert=active_alert)
        
        if user_role in ['activities', 'sport_coordinator']:
            return render_template('home/activities.html', user_name=user_name, active_alert=active_alert)
        
        if user_role == 'office':
            return render_template('home/office.html', user_name=user_name, active_alert=active_alert)
        
        if user_role in ['teacher', 'grade_head', 'admin']:
            return render_template('home/staff.html', user_name=user_name, active_alert=active_alert)
        
        # Not logged in - show code entry form (PWA friendly)
        login_error = request.args.get('error')
        return render_template('home/login.html', error=login_error)

    @app.route('/principal/')
    def old_eagle_eye():
        return redirect('/dashboard/')
    
    @app.route('/firebase-messaging-sw.js')
    def firebase_sw():
        return app.send_static_file('firebase-messaging-sw.js')
    

    @app.route('/login-code', methods=['POST'])
    def login_code():
        code = request.form.get('code', '').strip().lower()
        if code:
            from app.services.db import get_connection
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT us.*, sv.venue_id as default_venue_id, v.venue_name as default_venue_name
                    FROM user_session us
                    LEFT JOIN staff_venue sv ON us.staff_id = sv.staff_id
                    LEFT JOIN venue v ON sv.venue_id = v.id
                    WHERE us.magic_code = ? AND us.tenant_id = ?
                """, (code, TENANT_ID))
                row = cursor.fetchone()
                if row:
                    session['staff_id'] = row['staff_id']
                    session['display_name'] = row['display_name']
                    session['role'] = row['role']
                    session['can_resolve'] = bool(row['can_resolve'])
                    session['default_venue_id'] = row['default_venue_id']
                    session['default_venue_name'] = row['default_venue_name']
                    session['tenant_id'] = TENANT_ID
                    return redirect('/')
        return redirect('/?error=invalid')

    return app

