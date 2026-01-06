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
        <div style="font-family: system-ui; padding: 40px; max-width: 400px; margin: 0 auto;">
            <h1 style="font-size: 24px; margin-bottom: 20px;">SchoolOps</h1>
            <a href="/attendance/" style="display: block; padding: 16px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px; text-align: center; margin-bottom: 12px;">📋 Roll Call (Teachers)</a>
            <a href="/admin/" style="display: block; padding: 16px; background: #6b7280; color: white; text-decoration: none; border-radius: 8px; text-align: center;">⚙️ Admin Dashboard</a>
        </div>
        '''
    
    return app
