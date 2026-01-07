"""
SchoolOps Flask Application
"""
from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    
    # Register blueprints
    from app.routes.attendance import attendance_bp
    from app.routes.admin import admin_bp
    
    app.register_blueprint(attendance_bp)
    app.register_blueprint(admin_bp)
    
    @app.route('/')
    def home():
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="default">
    <title>SchoolOps</title>
    <link rel="apple-touch-icon" href="/static/icon-192.png">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
            min-height: 100vh;
            padding: 60px 20px 40px;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
            color: #1E293B;
        }
        .header h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .header p {
            font-size: 14px;
            opacity: 0.9;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            max-width: 400px;
            margin: 0 auto;
        }
        @media (min-width: 768px) {
            .grid {
                grid-template-columns: repeat(6, 1fr);
                max-width: 600px;
                gap: 24px;
            }
        }
        .app-icon {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-decoration: none;
            -webkit-tap-highlight-color: transparent;
        }
        .app-icon:active .icon-box {
            transform: scale(0.92);
        }
        .icon-box {
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
        }
        @media (min-width: 768px) {
            .icon-box {
                width: 72px;
                height: 72px;
                border-radius: 16px;
                font-size: 32px;
            }
        }
        .app-label {
            font-size: 11px;
            color: #1E293B;
            text-align: center;
            max-width: 70px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }
        @media (min-width: 768px) {
            .app-label { font-size: 12px; max-width: 80px; }
        }
        .bg-blue { background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); }
        .bg-green { background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); }
        .bg-orange { background: linear-gradient(135deg, #f97316 0%, #ea580c 100%); }
        .bg-purple { background: linear-gradient(135deg, #a855f7 0%, #9333ea 100%); }
        .bg-red { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
        .bg-gray { background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%); }
        .bg-teal { background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%); }
        .bg-pink { background: linear-gradient(135deg, #ec4899 0%, #db2777 100%); }
        
        /* Admin only on tablet/desktop */
        .desktop-only { display: none; }
        @media (min-width: 768px) {
            .desktop-only { display: flex; }
        }
        
        /* Coming soon - grayed out */
        .coming-soon .icon-box {
            opacity: 0.4;
        }
        .coming-soon .app-label {
            opacity: 0.6;
        }
        
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #1E293B;
            opacity: 0.7;
            font-size: 12px;
        }
        
        /* Badge */
        .icon-box { position: relative; }
        .badge {
            position: absolute;
            top: -6px;
            right: -6px;
            background: #ef4444;
            color: #1E293B;
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
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>SchoolOps</h1>
        <p>Maragon Mooikloof</p>
    </div>
    
    <div class="grid">
        <!-- Roll Call - All devices -->
        <a href="/attendance/" class="app-icon">
            <div class="icon-box bg-blue">📋</div>
            <span class="app-label">Roll Call</span>
        </a>
        
        <!-- Admin - Desktop/Tablet only -->
        <a href="/admin/" class="app-icon desktop-only">
            <div class="icon-box bg-gray">📊</div>
            <span class="app-label">Admin</span>
        </a>
        
        <!-- Coming Soon -->
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-orange">🔄</div>
            <span class="app-label">Substitutes</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-green">🚶</div>
            <span class="app-label">Duty</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-purple">📄</div>
            <span class="app-label">Documents</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-teal">📅</div>
            <span class="app-label">Timetable</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-red">⚽</div>
            <span class="app-label">Sports</span>
        </a>
        
        <a href="#" class="app-icon coming-soon" onclick="return false;">
            <div class="icon-box bg-pink">🔔</div>
            <span class="app-label">Alerts</span>
        </a>
    </div>
    
    <div class="footer">Term 1 2026 Pilot</div>
</body>
</html>
'''
    
    return app
