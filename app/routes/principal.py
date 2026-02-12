"""
Principal routes - Management Dashboard
Real-time school-wide attendance visibility for leadership.
Performance-first design: <100ms target with parallel API calls.
"""

from flask import Blueprint, render_template, jsonify
from datetime import date, datetime, timedelta
from app.services.db import get_connection

principal_bp = Blueprint('principal', __name__, url_prefix='/principal')

TENANT_ID = "MARAGON"


@principal_bp.route('/')
def dashboard():
    """Main Leadership dashboard page."""
    today = date.today()
    today_display = today.strftime('%A, %d %B %Y')
    return render_template('principal/dashboard.html', today_display=today_display)


@principal_bp.route('/api/stats')
def api_stats():
    """Get today's overall attendance stats."""
    today_str = date.today().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get total learners
        cursor.execute("SELECT COUNT(*) FROM learner WHERE tenant_id = ? AND is_active = 1", 
                      (TENANT_ID,))
        total_learners = cursor.fetchone()[0]
        
        # Get total mentor groups
        cursor.execute("SELECT COUNT(*) FROM mentor_group WHERE tenant_id = ?", (TENANT_ID,))
        total_groups = cursor.fetchone()[0]
        
        # Get submitted count for today
        cursor.execute("""
            SELECT COUNT(*) FROM attendance 
            WHERE tenant_id = ? AND date = ? AND status = 'Submitted'
        """, (TENANT_ID, today_str))
        submitted_count = cursor.fetchone()[0]
        
        # Get today's attendance entries stats
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN ae.status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN ae.status = 'Absent' THEN 1 ELSE 0 END) as absent,
                SUM(CASE WHEN ae.status = 'Late' THEN 1 ELSE 0 END) as late
            FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            WHERE a.tenant_id = ? AND a.date = ?
        """, (TENANT_ID, today_str))
        
        row = cursor.fetchone()
        present = row['present'] or 0
        absent = row['absent'] or 0
        late = row['late'] or 0
        
        # Calculate attendance rate
        marked_total = present + absent + late
        attendance_rate = round((present / marked_total) * 100, 1) if marked_total > 0 else 0
    
    return jsonify({
        "total_learners": total_learners,
        "total_groups": total_groups,
        "submitted_count": submitted_count,
        "pending_count": total_groups - submitted_count,
        "present": present,
        "absent": absent,
        "late": late,
        "attendance_rate": attendance_rate
    })


@principal_bp.route('/api/pending')
def api_pending():
    """Get list of classes with pending registers."""
    today_str = date.today().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                mg.id,
                mg.group_name,
                g.grade_name,
                s.display_name as mentor_name
            FROM mentor_group mg
            LEFT JOIN grade g ON mg.grade_id = g.id
            LEFT JOIN staff s ON mg.mentor_id = s.id
            LEFT JOIN attendance a ON mg.id = a.mentor_group_id AND a.date = ?
            WHERE mg.tenant_id = ? AND a.id IS NULL
            ORDER BY g.grade_number, mg.group_name
        """, (today_str, TENANT_ID))
        
        pending = [dict(row) for row in cursor.fetchall()]
    
    return jsonify({"pending": pending, "count": len(pending)})


@principal_bp.route('/api/weekly-trend')
def api_weekly_trend():
    """Get last 5 school days attendance trend."""
    today = date.today()
    
    # Get last 5 school days (skip weekends)
    school_days = []
    check_date = today
    while len(school_days) < 5:
        if check_date.weekday() < 5:  # Monday=0 to Friday=4
            school_days.append(check_date)
        check_date -= timedelta(days=1)
    
    school_days.reverse()  # Oldest to newest
    
    trend_data = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        for day in school_days:
            day_str = day.isoformat()
            day_label = day.strftime('%a')  # Mon, Tue, etc.
            
            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN ae.status = 'Present' THEN 1 ELSE 0 END) as present,
                    SUM(CASE WHEN ae.status = 'Absent' THEN 1 ELSE 0 END) as absent,
                    SUM(CASE WHEN ae.status = 'Late' THEN 1 ELSE 0 END) as late
                FROM attendance_entry ae
                JOIN attendance a ON ae.attendance_id = a.id
                WHERE a.tenant_id = ? AND a.date = ?
            """, (TENANT_ID, day_str))
            
            row = cursor.fetchone()
            present = row['present'] or 0
            absent = row['absent'] or 0
            late = row['late'] or 0
            
            total = present + absent + late
            rate = round((present / total) * 100, 1) if total > 0 else 0
            
            trend_data.append({
                "date": day_str,
                "day": day_label,
                "present": present,
                "absent": absent,
                "late": late,
                "rate": rate
            })
    
    return jsonify({"trend": trend_data})


@principal_bp.route('/api/grade-comparison')
def api_grade_comparison():
    """Get attendance comparison by grade."""
    today_str = date.today().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                g.grade_name,
                g.grade_number,
                COUNT(CASE WHEN ae.status = 'Present' THEN 1 END) as present,
                COUNT(CASE WHEN ae.status = 'Absent' THEN 1 END) as absent,
                COUNT(CASE WHEN ae.status = 'Late' THEN 1 END) as late
            FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            JOIN mentor_group mg ON a.mentor_group_id = mg.id
            JOIN grade g ON mg.grade_id = g.id
            WHERE a.tenant_id = ? AND a.date = ?
            GROUP BY g.id
            ORDER BY g.grade_number
        """, (TENANT_ID, today_str))
        
        grades = []
        for row in cursor.fetchall():
            total = (row['present'] or 0) + (row['absent'] or 0) + (row['late'] or 0)
            rate = round(((row['present'] or 0) / total) * 100, 1) if total > 0 else 0
            
            grades.append({
                "grade_name": row['grade_name'],
                "grade_number": row['grade_number'],
                "present": row['present'] or 0,
                "absent": row['absent'] or 0,
                "late": row['late'] or 0,
                "rate": rate
            })
    
    return jsonify({"grades": grades})


@principal_bp.route('/api/welfare-watchlist')
def api_welfare_watchlist():
    """Get learners with 3+ consecutive absent days."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                t.learner_id,
                t.consecutive_absent_days,
                t.last_attendance_date,
                l.first_name,
                l.surname,
                mg.group_name,
                g.grade_name
            FROM learner_absent_tracking t
            JOIN learner l ON t.learner_id = l.id
            JOIN mentor_group mg ON l.mentor_group_id = mg.id
            LEFT JOIN grade g ON mg.grade_id = g.id
            WHERE t.tenant_id = ? AND t.consecutive_absent_days >= 3
            ORDER BY t.consecutive_absent_days DESC
            LIMIT 10
        """, (TENANT_ID,))
        
        watchlist = [dict(row) for row in cursor.fetchall()]
    
    return jsonify({"watchlist": watchlist, "count": len(watchlist)})


@principal_bp.route('/api/chronic-absentees')
def api_chronic_absentees():
    """Get learners with >20% absence rate over last 10 days."""
    today = date.today()
    
    # Get start date (10 school days ago)
    start_date = today - timedelta(days=14)  # Approximate, includes weekends
    start_str = start_date.isoformat()
    today_str = today.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                l.id as learner_id,
                l.first_name,
                l.surname,
                mg.group_name,
                g.grade_name,
                COUNT(CASE WHEN ae.status = 'Absent' THEN 1 END) as absent_count,
                COUNT(ae.id) as total_days,
                ROUND(CAST(COUNT(CASE WHEN ae.status = 'Absent' THEN 1 END) AS FLOAT) / 
                      NULLIF(COUNT(ae.id), 0) * 100, 1) as absence_rate
            FROM learner l
            JOIN attendance_entry ae ON l.id = ae.learner_id
            JOIN attendance a ON ae.attendance_id = a.id
            JOIN mentor_group mg ON l.mentor_group_id = mg.id
            LEFT JOIN grade g ON mg.grade_id = g.id
            WHERE a.tenant_id = ? AND a.date BETWEEN ? AND ?
            GROUP BY l.id
            HAVING absence_rate > 20
            ORDER BY absence_rate DESC
            LIMIT 10
        """, (TENANT_ID, start_str, today_str))
        
        absentees = [dict(row) for row in cursor.fetchall()]
    
    return jsonify({"absentees": absentees, "count": len(absentees)})
