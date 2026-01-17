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
    
    @app.before_request
    def check_password_gate():
        if request.path.startswith('/static') or request.path == '/gate':
            return
        if session.get('gate_passed'):
            return
        if request.method == 'POST' and request.path == '/gate':
            return
        return redirect('/gate')
    
    @app.route('/gate', methods=['GET', 'POST'])
    def password_gate():
        error = None
        if request.method == 'POST':
            password = request.form.get('password', '')
            if password == 'maragon2026':
                session['gate_passed'] = True
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
        if magic_code and 'staff_id' not in session:
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
        active_alert = None
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, alert_type, location_display FROM emergency_alert WHERE tenant_id = ? AND status = 'Active' ORDER BY triggered_at DESC LIMIT 1", (TENANT_ID,))
            row = cursor.fetchone()
            if row:
                active_alert = dict(row)
        
        user_name = session.get('display_name', '')
        user_logged_in = 'staff_id' in session
        user_role = session.get('role', 'teacher')
        
        # Leadership gets their own home page
        if user_role in ['principal', 'deputy']:
            return render_template('home/leadership.html', user_name=user_name, active_alert=active_alert)
        
        show_dashboard = user_role in ['principal', 'deputy', 'admin']
        show_admin = user_logged_in  # Dev: all magic link users
        
        icons_html = f'''
        <a href="/emergency/" class="app-icon">
            <div class="icon-box bg-red {'emergency-pulse' if active_alert else ''}">&#128680;</div>
            <span class="app-label">Emergency</span>
        </a>
        <a href="/attendance/" class="app-icon">
            <div class="icon-box bg-blue">&#128203;</div>
            <span class="app-label">Roll Call</span>
        </a>
        <a href="/substitute/report" class="app-icon">
            <div class="icon-box bg-orange">✋</div>
            <span class="app-label">Report Absence</span>
        </a>
        <a href="/duty/my-day" class="app-icon">
            <div class="icon-box bg-green">&#128694;</div>
            <span class="app-label">My Day</span>
        </a>
        <a href="/substitute/sub-duties" class="app-icon">
            <div class="icon-box bg-cyan">📅</div>
            <span class="app-label">Sub Duties</span>
        </a>
        <a href="/sport/events" class="app-icon">
            <div class="icon-box bg-teal">&#127942;</div>
            <span class="app-label">Sport</span>
        </a>
        '''
        
        if show_dashboard:
            icons_html += '''
        <a href="/dashboard/" class="app-icon">
            <div class="icon-box bg-indigo">&#128200;</div>
            <span class="app-label">Dashboard</span>
        </a>
        '''
        
        if show_admin:
            icons_html += '''
        <a href="/admin/" class="app-icon">
            <div class="icon-box bg-amber">📒</div>
            <span class="app-label">Registers</span>
        </a>
        '''
        
        icons_html += '''
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-purple">&#128196;</div>
            <span class="app-label">Documents</span>
        </a>
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-teal">&#128197;</div>
            <span class="app-label">Timetable</span>
        </a>
        '''
        
        return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <title>SchoolOps</title>
    <link rel="manifest" href="/static/manifest.json">
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-app-compat.js"></script>
    <script src="https://www.gstatic.com/firebasejs/10.7.1/firebase-messaging-compat.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%); min-height: 100vh; padding: 60px 20px 40px; }}
        .user-bar {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(255,255,255,0.95); padding: 12px 20px; font-size: 14px; color: #1E293B; z-index: 100; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .user-bar a {{ color: #3b82f6; text-decoration: none; }}
        .header {{ text-align: center; margin-bottom: 40px; color: #1E293B; padding-top: 20px; }}
        .header h1 {{ font-size: 28px; font-weight: 600; margin-bottom: 4px; }}
        .header p {{ font-size: 14px; opacity: 0.9; }}
        .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; max-width: 400px; margin: 0 auto; }}
        @media (min-width: 768px) {{ .grid {{ grid-template-columns: repeat(6, 1fr); max-width: 600px; gap: 24px; }} }}
        .app-icon {{ display: flex; flex-direction: column; align-items: center; text-decoration: none; -webkit-tap-highlight-color: transparent; }}
        .app-icon:active .icon-box {{ transform: scale(0.92); }}
        .icon-box {{ width: 60px; height: 60px; border-radius: 14px; display: flex; align-items: center; justify-content: center; font-size: 28px; margin-bottom: 6px; transition: transform 0.1s; box-shadow: 0 4px 12px rgba(0,0,0,0.15); position: relative; }}
        @media (min-width: 768px) {{ .icon-box {{ width: 72px; height: 72px; border-radius: 16px; font-size: 32px; }} }}
        .app-label {{ font-size: 11px; color: #1E293B; text-align: center; max-width: 70px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
        @media (min-width: 768px) {{ .app-label {{ font-size: 12px; max-width: 80px; }} }}
        .bg-blue {{ background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }}
        .bg-green {{ background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }}
        .bg-orange {{ background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }}
        .bg-purple {{ background: linear-gradient(135deg, #a855f7 0%, #9333ea 100%); }}
        .bg-red {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }}
        .bg-gray {{ background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); }}
        .bg-teal {{ background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%); }}
        .bg-indigo {{ background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }}
        .bg-cyan {{ background: linear-gradient(135deg, #06b6d4 0%, #0891b2 100%); }}
        .coming-soon .icon-box {{ opacity: 0.4; }}
        .coming-soon .app-label {{ opacity: 0.6; }}
        .footer {{ text-align: center; margin-top: 50px; color: #1E293B; opacity: 0.7; font-size: 12px; }}
        .emergency-pulse {{ animation: pulse-red 1.5s infinite; }}
        @keyframes pulse-red {{ 0%, 100% {{ box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4); }} 50% {{ box-shadow: 0 4px 20px rgba(239, 68, 68, 0.8); }} }}
        .push-prompt {{ position: fixed; bottom: 20px; left: 20px; right: 20px; background: #1e293b; color: white; padding: 16px 20px; border-radius: 12px; display: none; align-items: center; justify-content: space-between; gap: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); z-index: 1000; }}
        .push-prompt.show {{ display: flex; }}
        .push-prompt-text {{ flex: 1; font-size: 14px; }}
        .push-prompt-btn {{ padding: 8px 16px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }}
        .push-prompt-btn.allow {{ background: #22c55e; color: white; }}
        .push-prompt-btn.dismiss {{ background: transparent; color: #94a3b8; }}
    </style>
</head>
<body>
    <div class="user-bar">
        <span>{'&#128100; ' + user_name if user_logged_in else 'Not logged in'}</span>
        {'<a href="/admin/seed-emergency">Setup</a>' if user_logged_in else '<span style="opacity:0.5">Use magic link to login</span>'}
    </div>
    <div id="alert-banner" hx-get="/emergency/banner" hx-trigger="load, every 5s" hx-swap="innerHTML"></div>
    <div class="header">
        <h1>SchoolOps</h1>
        <p>Maragon Mooikloof</p>
    </div>
    <div class="grid">{icons_html}</div>
    <div class="footer">Term 1 2026 Pilot</div>
    <div class="push-prompt" id="pushPrompt">
        <span class="push-prompt-text">🔔 Enable notifications to receive emergency alerts</span>
        <button class="push-prompt-btn dismiss" onclick="dismissPushPrompt()">Later</button>
        <button class="push-prompt-btn allow" onclick="enablePushNotifications()">Enable</button>
    </div>
    <script src="/static/push.js"></script>
    <script>
        function checkPushPrompt() {{ if (!('Notification' in window)) return; if (!('serviceWorker' in navigator)) return; if (Notification.permission !== 'default') return; if (localStorage.getItem('push_prompt_dismissed')) return; setTimeout(() => {{ document.getElementById('pushPrompt').classList.add('show'); }}, 2000); }}
        async function enablePushNotifications() {{ document.getElementById('pushPrompt').classList.remove('show'); const granted = await requestNotificationPermission(); if (granted) {{ console.log('Push notifications enabled!'); }} }}
        function dismissPushPrompt() {{ document.getElementById('pushPrompt').classList.remove('show'); localStorage.setItem('push_prompt_dismissed', 'true'); }}
        {'checkPushPrompt();' if user_logged_in else ''}
    </script>
</body>
</html>
'''
    
    @app.route('/principal/')
    def old_eagle_eye():
        return redirect('/dashboard/')
    
    @app.route('/firebase-messaging-sw.js')
    def firebase_sw():
        return app.send_static_file('firebase-messaging-sw.js')
    
    return app
