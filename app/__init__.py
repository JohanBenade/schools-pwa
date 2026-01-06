"""
SchoolOps Flask Application
"""
from flask import Flask, render_template
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
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>SchoolOps</title>
            <style>
                * { box-sizing: border-box; }
                body { font-family: system-ui; padding: 40px 20px; max-width: 400px; margin: 0 auto; background: #f9fafb; }
                h1 { font-size: 28px; margin-bottom: 8px; color: #1f2937; }
                .subtitle { color: #6b7280; margin-bottom: 24px; }
                .btn { display: block; padding: 20px; color: white; text-decoration: none; border-radius: 12px; text-align: center; margin-bottom: 12px; }
                .btn-blue { background: #2563eb; }
                .btn-gray { background: #374151; }
                .btn-icon { font-size: 32px; display: block; margin-bottom: 8px; }
                .btn-label { font-size: 18px; font-weight: 600; }
                .btn-desc { font-size: 12px; opacity: 0.8; margin-top: 4px; }
                .admin-btn { display: none; }
                @media (min-width: 768px) { .admin-btn { display: block; } }
                .footer { text-align: center; color: #9ca3af; font-size: 12px; margin-top: 32px; }
            </style>
        </head>
        <body>
            <h1>SchoolOps</h1>
            <p class="subtitle">Maragon Mooikloof</p>
            
            <a href="/attendance/" class="btn btn-blue">
                <span class="btn-icon">📋</span>
                <span class="btn-label">Roll Call</span>
                <span class="btn-desc">Take attendance</span>
            </a>
            
            <a href="/admin/" class="btn btn-gray admin-btn">
                <span class="btn-icon">📊</span>
                <span class="btn-label">Admin Dashboard</span>
                <span class="btn-desc">View submissions & STASY capture</span>
            </a>
            
            <p class="footer">Term 1 2026 Pilot</p>
        </body>
        </html>
        '''
    
    return app
