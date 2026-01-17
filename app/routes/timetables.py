"""
Timetables routes - Leadership view of any teacher's schedule
"""

from flask import Blueprint, render_template, session, redirect
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

timetables_bp = Blueprint('timetables', __name__, url_prefix='/timetables')

TENANT_ID = "MARAGON"


@timetables_bp.route('/')
def index():
    """Teacher search page for leadership."""
    role = session.get('role', 'teacher')
    if role not in ['principal', 'deputy', 'admin']:
        return redirect('/')
    
    # Get all teachers
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, display_name, role
            FROM staff
            WHERE tenant_id = ? AND is_active = 1
            ORDER BY display_name
        """, (TENANT_ID,))
        teachers = [dict(row) for row in cursor.fetchall()]
    
    nav_header = get_nav_header("Timetables", "/", "Home")
    nav_styles = get_nav_styles()
    
    return render_template('timetables/index.html',
                          teachers=teachers,
                          nav_header=nav_header,
                          nav_styles=nav_styles)
