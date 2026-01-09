"""
SchoolOps Flask Application
"""
from flask import Flask, session, request, redirect
from dotenv import load_dotenv
import os

load_dotenv()

TENANT_ID = "MARAGON"


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    
    # Register blueprints
    from app.routes.attendance import attendance_bp
    from app.routes.admin import admin_bp
    from app.routes.principal import principal_bp
    from app.routes.emergency import emergency_bp
    
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(principal_bp)
    app.register_blueprint(emergency_bp)
    
    @app.before_request
    def handle_magic_link():
        """Handle magic link login via ?u= parameter."""
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
            
            # Redirect to clean URL
            clean_url = request.path
            return redirect(clean_url)
    
    @app.context_processor
    def inject_user():
        """Make user info available to all templates."""
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
        # Check for active emergency alert
        from app.services.db import get_connection
        active_alert = None
        
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, alert_type, location_display 
                FROM emergency_alert 
                WHERE tenant_id = ? AND status = 'Active'
                ORDER BY triggered_at DESC LIMIT 1
            """, (TENANT_ID,))
            row = cursor.fetchone()
            if row:
                active_alert = dict(row)
        
        user_name = session.get('display_name', '')
        user_logged_in = 'staff_id' in session
        
        return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <title>SchoolOps</title>
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
            min-height: 100vh;
            padding: 60px 20px 40px;
        }}
        .user-bar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: rgba(255,255,255,0.95);
            padding: 12px 20px;
            font-size: 14px;
            color: #1E293B;
            z-index: 100;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .user-bar a {{
            color: #3b82f6;
            text-decoration: none;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            color: #1E293B;
            padding-top: 20px;
        }}
        .header h1 {{
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 4px;
        }}
        .header p {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            max-width: 400px;
            margin: 0 auto;
        }}
        @media (min-width: 768px) {{
            .grid {{
                grid-template-columns: repeat(6, 1fr);
                max-width: 600px;
                gap: 24px;
            }}
        }}
        .app-icon {{
            display: flex;
            flex-direction: column;
            align-items: center;
            text-decoration: none;
            -webkit-tap-highlight-color: transparent;
        }}
        .app-icon:active .icon-box {{
            transform: scale(0.92);
        }}
        .icon-box {{
            width: 60px;
            height: 60px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            margin-bottom: 6px;
            transition: transform 0.1s;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            position: relative;
        }}
        @media (min-width: 768px) {{
            .icon-box {{
                width: 72px;
                height: 72px;
                border-radius: 16px;
                font-size: 32px;
            }}
        }}
        .app-label {{
            font-size: 11px;
            color: #1E293B;
            text-align: center;
            max-width: 70px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}
        @media (min-width: 768px) {{
            .app-label {{ font-size: 12px; max-width: 80px; }}
        }}
        .bg-blue {{ background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }}
        .bg-green {{ background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }}
        .bg-orange {{ background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }}
        .bg-purple {{ background: linear-gradient(135deg, #a855f7 0%, #9333ea 100%); }}
        .bg-red {{ background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }}
        .bg-gray {{ background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); }}
        .bg-teal {{ background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%); }}
        .bg-pink {{ background: linear-gradient(135deg, #ec4899 0%, #db2777 100%); }}
        .bg-indigo {{ background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); }}
        
        .coming-soon .icon-box {{
            opacity: 0.4;
        }}
        .coming-soon .app-label {{
            opacity: 0.6;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 50px;
            color: #1E293B;
            opacity: 0.7;
            font-size: 12px;
        }}
        
        .badge {{
            position: absolute;
            top: -6px;
            right: -6px;
            background: #ef4444;
            color: white;
            font-size: 12px;
            font-weight: 600;
            min-width: 20px;
            height: 20px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 6px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        
        /* Emergency icon pulsing */
        .emergency-pulse {{
            animation: pulse-red 1.5s infinite;
        }}
        @keyframes pulse-red {{
            0%, 100% {{ box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4); }}
            50% {{ box-shadow: 0 4px 20px rgba(239, 68, 68, 0.8); }}
        }}
    </style>
</head>
<body>
    <div class="user-bar">
        <span>{'&#128100; ' + user_name if user_logged_in else 'Not logged in'}</span>
        {'<a href="/admin/seed-emergency">Setup</a>' if user_logged_in else '<span style="opacity:0.5">Use magic link to login</span>'}
    </div>
    
    <!-- Alert banner placeholder - polled via HTMX -->
    <div id="alert-banner" 
         hx-get="/emergency/banner" 
         hx-trigger="load, every 5s"
         hx-swap="innerHTML">
    </div>
    
    <div class="header">
        <h1>SchoolOps</h1>
        <p>Maragon Mooikloof</p>
    </div>
    
    <div class="grid">
        <!-- Emergency - Primary for demo -->
        <a href="/emergency/" class="app-icon">
            <div class="icon-box bg-red {'emergency-pulse' if {active_alert} else ''}">&#128680;</div>
            <span class="app-label">Emergency</span>
        </a>
        
        <!-- Roll Call -->
        <a href="/attendance/" class="app-icon">
            <div class="icon-box bg-blue">&#128203;</div>
            <span class="app-label">Roll Call</span>
        </a>
        
        <!-- Eagle Eye - Principal Dashboard -->
        <a href="/principal/" class="app-icon">
            <div class="icon-box bg-indigo">&#129413;</div>
            <span class="app-label">Eagle Eye</span>
        </a>
        
        <!-- Admin -->
        <a href="/admin/" class="app-icon">
            <div class="icon-box bg-gray">&#128202;</div>
            <span class="app-label">Admin</span>
        </a>
        
        <!-- Coming Soon -->
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-orange">&#128260;</div>
            <span class="app-label">Substitutes</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-green">&#128694;</div>
            <span class="app-label">Duty</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-purple">&#128196;</div>
            <span class="app-label">Documents</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-teal">&#128197;</div>
            <span class="app-label">Timetable</span>
        </a>
    </div>
    
    <div class="footer">Term 1 2026 Pilot</div>
</body>
</html>
'''
    
    return app
