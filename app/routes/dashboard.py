"""
Management Dashboard - Principal, Deputy, Admin view
"""

from flask import Blueprint, session, redirect
from datetime import date
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

TENANT_ID = "MARAGON"


@dashboard_bp.route('/')
def index():
    user_role = session.get('role', 'teacher')
    if user_role not in ['principal', 'deputy', 'admin']:
        return redirect('/')
    
    today = date.today()
    today_str = today.isoformat()
    today_display = today.strftime('%A, %d %B %Y')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM mentor_group WHERE tenant_id = ?', (TENANT_ID,))
        total_groups = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM attendance WHERE tenant_id = ? AND date = ?', (TENANT_ID, today_str))
        submitted_count = cursor.fetchone()[0]
        
        pending_count = total_groups - submitted_count
        
        # Get pending classes - simple query
        cursor.execute('''
            SELECT mg.group_name
            FROM mentor_group mg
            WHERE mg.tenant_id = ? AND mg.id NOT IN (
                SELECT mentor_group_id FROM attendance WHERE date = ? AND tenant_id = ?
            )
            ORDER BY mg.group_name
            LIMIT 5
        ''', (TENANT_ID, today_str, TENANT_ID))
        pending_classes = [row['group_name'] for row in cursor.fetchall()]
        
        cursor.execute('''
            SELECT COUNT(*) FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            WHERE a.date = ? AND a.tenant_id = ? AND ae.status = 'Absent'
        ''', (today_str, TENANT_ID))
        absent_learners = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT ea.*, s.display_name as triggered_by_name,
                   (SELECT COUNT(*) FROM emergency_response er WHERE er.alert_id = ea.id) as responder_count
            FROM emergency_alert ea
            LEFT JOIN staff s ON ea.triggered_by_id = s.id
            WHERE ea.tenant_id = ? AND ea.status = 'Active'
            ORDER BY ea.triggered_at DESC LIMIT 1
        ''', (TENANT_ID,))
        row = cursor.fetchone()
        active_emergency = dict(row) if row else None
        
        cursor.execute('''
            SELECT a.*, s.display_name as teacher_name,
                   (SELECT COUNT(*) FROM substitute_request sr 
                    WHERE sr.absence_id = a.id AND sr.status = 'Assigned') as covered_count,
                   (SELECT COUNT(*) FROM substitute_request sr WHERE sr.absence_id = a.id) as total_periods
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            WHERE a.absence_date = ? AND a.tenant_id = ?
            ORDER BY a.reported_at DESC
        ''', (today_str, TENANT_ID))
        absences = [dict(row) for row in cursor.fetchall()]
        
        total_absences = len(absences)
        gaps = sum(a['total_periods'] - a['covered_count'] for a in absences)
    
    emergency_html = ""
    if active_emergency:
        emergency_html = f'''
            <div class="big-number">1</div>
            <div class="big-label">active emergency</div>
            <div class="detail-list">
                <div class="detail-item">📍 {active_emergency['location_display'] or 'Unknown'}</div>
                <div class="detail-item">🏷️ {active_emergency['alert_type']}</div>
                <div class="detail-item">👤 {active_emergency['triggered_by_name']}</div>
                <div class="detail-item">🙋 {active_emergency['responder_count']} responding</div>
            </div>
            <a href="/emergency/" class="card-link">View Emergency →</a>
        '''
    else:
        emergency_html = '''
            <div class="big-number" style="color: #22c55e;">✓</div>
            <div class="big-label">No active emergencies</div>
            <a href="/emergency/" class="card-link">Emergency Center →</a>
        '''
    
    absences_html = ""
    if absences:
        rows = ''.join(f'<div class="absence-row"><span class="absence-name">{a["teacher_name"]}</span><span class="absence-status">{a["covered_count"]}/{a["total_periods"]}</span></div>' for a in absences[:3])
        absences_html = f'<div class="detail-list">{rows}</div>'
    else:
        absences_html = '<div class="detail-list"><div class="detail-item" style="color: #22c55e;">✓ No absences reported</div></div>'
    
    pending_html = ""
    if pending_classes:
        names = ', '.join(pending_classes[:3]) + ('...' if len(pending_classes) > 3 else '')
        pending_html = f'<div class="detail-list"><div class="detail-item">⏳ {names}</div></div>'
    
    nav_header = get_nav_header("Dashboard", "/", "Home")
    nav_styles = get_nav_styles()
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - SchoolOps</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; padding: 20px; color: white; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        {nav_styles}
        .header-date {{ font-size: 14px; opacity: 0.7; text-align: center; margin-bottom: 20px; }}
        .cards {{ display: flex; flex-direction: column; gap: 16px; }}
        .card {{ background: rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .card-title {{ font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8; }}
        .card-status {{ padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .status-green {{ background: #22c55e; }}
        .status-yellow {{ background: #eab308; color: #000; }}
        .status-red {{ background: #ef4444; }}
        .big-number {{ font-size: 48px; font-weight: 700; line-height: 1; }}
        .big-label {{ font-size: 14px; opacity: 0.7; margin-top: 4px; }}
        .stat-row {{ display: flex; gap: 24px; margin-top: 16px; }}
        .stat {{ flex: 1; }}
        .stat-value {{ font-size: 24px; font-weight: 600; }}
        .stat-label {{ font-size: 12px; opacity: 0.6; }}
        .detail-list {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1); }}
        .detail-item {{ font-size: 13px; padding: 6px 0; opacity: 0.8; }}
        .card-link {{ display: block; text-align: center; margin-top: 16px; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 8px; color: white; text-decoration: none; font-size: 14px; }}
        .card-link:hover {{ background: rgba(255,255,255,0.15); }}
        .emergency-active {{ background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); animation: pulse-border 2s infinite; }}
        @keyframes pulse-border {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }} 50% {{ box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }} }}
        .absence-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .absence-row:last-child {{ border-bottom: none; }}
        .absence-name {{ font-weight: 500; }}
        .absence-status {{ font-size: 12px; padding: 2px 8px; border-radius: 8px; background: #22c55e; }}
    </style>
</head>
<body>
    <div class="container">
        {nav_header}
        <div class="header-date">{today_display}</div>
        
        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📋 Attendance</span>
                    <span class="card-status {'status-green' if pending_count == 0 else 'status-yellow' if pending_count <= 3 else 'status-red'}">{'All In' if pending_count == 0 else f'{pending_count} Pending'}</span>
                </div>
                <div class="big-number">{submitted_count}/{total_groups}</div>
                <div class="big-label">registers submitted</div>
                <div class="stat-row">
                    <div class="stat"><div class="stat-value">{absent_learners}</div><div class="stat-label">learners absent</div></div>
                    <div class="stat"><div class="stat-value">{pending_count}</div><div class="stat-label">outstanding</div></div>
                </div>
                {pending_html}
                <a href="/admin/" class="card-link">View Details →</a>
            </div>
            
            <div class="card {'emergency-active' if active_emergency else ''}">
                <div class="card-header">
                    <span class="card-title">🚨 Emergencies</span>
                    <span class="card-status {'status-red' if active_emergency else 'status-green'}">{'ACTIVE' if active_emergency else 'All Clear'}</span>
                </div>
                {emergency_html}
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">👩‍🏫 Substitute Coverage</span>
                    <span class="card-status {'status-green' if gaps == 0 else 'status-yellow'}">{'All Covered' if gaps == 0 else f'{gaps} Gap{"s" if gaps != 1 else ""}'}</span>
                </div>
                <div class="big-number">{total_absences}</div>
                <div class="big-label">teacher{'s' if total_absences != 1 else ''} absent today</div>
                {absences_html}
                <a href="/substitute/mission-control" class="card-link">Mission Control →</a>
            </div>
        </div>
    </div>
</body>
</html>
'''
