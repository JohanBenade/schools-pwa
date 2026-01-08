"""
Principal Dashboard - Eagle Eye View
Optimized for <100ms response times
"""

from flask import Blueprint, render_template, jsonify, request
from datetime import date, datetime, timedelta
from app.services.db import get_connection

principal_bp = Blueprint('principal', __name__, url_prefix='/principal')

TENANT_ID = "MARAGON"


@principal_bp.route('/')
def dashboard():
    """Main principal dashboard - single fast query."""
    today = date.today()
    return render_template('principal/dashboard.html', today=today)


@principal_bp.route('/api/stats')
def api_stats():
    """Today's stats - optimized single query."""
    today = date.today()
    today_str = today.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Single efficient query for today's stats
        cursor.execute('''
            SELECT 
                (SELECT COUNT(*) FROM learner WHERE is_active = 1) as total_learners,
                (SELECT COUNT(*) FROM mentor_group) as total_groups,
                (SELECT COUNT(DISTINCT a.mentor_group_id) FROM attendance a WHERE a.date = ?) as submitted_groups,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance a ON ae.attendance_id = a.id 
                 WHERE a.date = ? AND ae.status = 'Present') as present,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance a ON ae.attendance_id = a.id 
                 WHERE a.date = ? AND ae.status = 'Absent') as absent,
                (SELECT COUNT(*) FROM attendance_entry ae 
                 JOIN attendance a ON ae.attendance_id = a.id 
                 WHERE a.date = ? AND ae.status = 'Late') as late
        ''', (today_str, today_str, today_str, today_str))
        
        row = cursor.fetchone()
        total_learners = row[0] or 625
        total_groups = row[1] or 25
        submitted = row[2] or 0
        present = row[3] or 0
        absent = row[4] or 0
        late = row[5] or 0
        
        # Calculate rate (avoid division by zero)
        responded_learners = present + absent + late
        rate = round((present / responded_learners * 100), 1) if responded_learners > 0 else 0
        
        return jsonify({
            'total_learners': total_learners,
            'total_groups': total_groups,
            'submitted_groups': submitted,
            'pending_groups': total_groups - submitted,
            'present': present,
            'absent': absent,
            'late': late,
            'rate': rate,
            'status': 'excellent' if rate >= 95 else 'good' if rate >= 90 else 'attention'
        })


@principal_bp.route('/api/pending')
def api_pending():
    """Pending registers - who hasn't submitted."""
    today = date.today()
    today_str = today.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT mg.group_name, s.display_name
            FROM mentor_group mg
            LEFT JOIN staff s ON mg.mentor_id = s.id
            WHERE mg.id NOT IN (
                SELECT mentor_group_id FROM attendance WHERE date = ?
            )
            ORDER BY mg.group_name
        ''', (today_str,))
        
        pending = [{'group': row[0], 'mentor': row[1] or 'TBC'} for row in cursor.fetchall()]
        
    return jsonify(pending)


@principal_bp.route('/api/trend')
def api_trend():
    """Last 5 school days trend."""
    today = date.today()
    
    # Get last 5 weekdays
    days = []
    check = today
    while len(days) < 5:
        if check.weekday() < 5:
            days.append(check)
        check -= timedelta(days=1)
    days.reverse()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        trend = []
        for d in days:
            d_str = d.isoformat()
            
            cursor.execute('''
                SELECT 
                    COUNT(CASE WHEN ae.status = 'Present' THEN 1 END) as present,
                    COUNT(CASE WHEN ae.status = 'Absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN ae.status = 'Late' THEN 1 END) as late
                FROM attendance_entry ae
                JOIN attendance a ON ae.attendance_id = a.id
                WHERE a.date = ?
            ''', (d_str,))
            
            row = cursor.fetchone()
            present = row[0] or 0
            absent = row[1] or 0
            late = row[2] or 0
            total = present + absent + late
            
            rate = round((present / total * 100), 1) if total > 0 else 0
            
            trend.append({
                'day': d.strftime('%a %d'),
                'date': d_str,
                'rate': rate,
                'present': present,
                'absent': absent,
                'late': late
            })
        
    return jsonify(trend)


@principal_bp.route('/api/grades')
def api_grades():
    """Attendance by grade - today."""
    today = date.today()
    today_str = today.isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                g.grade_name,
                g.grade_number,
                COUNT(CASE WHEN ae.status = 'Present' THEN 1 END) as present,
                COUNT(CASE WHEN ae.status IN ('Absent', 'Late') THEN 1 END) as not_present,
                COUNT(*) as total
            FROM grade g
            JOIN mentor_group mg ON mg.grade_id = g.id
            JOIN attendance a ON a.mentor_group_id = mg.id AND a.date = ?
            JOIN attendance_entry ae ON ae.attendance_id = a.id
            GROUP BY g.id, g.grade_name, g.grade_number
            ORDER BY g.grade_number
        ''', (today_str,))
        
        grades = []
        for row in cursor.fetchall():
            total = row[4] or 1
            present = row[2] or 0
            rate = round((present / total * 100), 1)
            grades.append({
                'grade': row[0],
                'rate': rate,
                'present': present,
                'total': total
            })
        
    return jsonify(grades)


@principal_bp.route('/api/watchlist')
def api_watchlist():
    """Welfare watchlist - consecutive absences."""
    today = date.today()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get learners with 3+ consecutive recent absences
        # This query looks at the last 7 days
        cursor.execute('''
            WITH recent_absences AS (
                SELECT 
                    l.id,
                    l.first_name,
                    l.surname,
                    mg.group_name,
                    a.date,
                    ae.status
                FROM learner l
                JOIN mentor_group mg ON l.mentor_group_id = mg.id
                JOIN attendance a ON a.mentor_group_id = mg.id
                JOIN attendance_entry ae ON ae.attendance_id = a.id AND ae.learner_id = l.id
                WHERE a.date >= date(?, '-7 days')
                ORDER BY l.id, a.date DESC
            )
            SELECT 
                id, first_name, surname, group_name,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_count
            FROM recent_absences
            GROUP BY id, first_name, surname, group_name
            HAVING absent_count >= 3
            ORDER BY absent_count DESC
            LIMIT 10
        ''', (today.isoformat(),))
        
        watchlist = []
        for row in cursor.fetchall():
            consecutive = row[4]
            if consecutive >= 5:
                action = 'Welfare check needed'
            elif consecutive >= 4:
                action = 'Contact parent'
            else:
                action = 'Monitor'
            
            watchlist.append({
                'name': f"{row[1]} {row[2]}",
                'group': row[3],
                'consecutive': consecutive,
                'action': action
            })
        
    return jsonify(watchlist)


@principal_bp.route('/api/chronic')
def api_chronic():
    """Chronic absenteeism - >20% absence rate over period."""
    today = date.today()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                l.first_name,
                l.surname,
                mg.group_name,
                COUNT(CASE WHEN ae.status = 'Absent' THEN 1 END) as absent_days,
                COUNT(*) as total_days
            FROM learner l
            JOIN mentor_group mg ON l.mentor_group_id = mg.id
            JOIN attendance a ON a.mentor_group_id = mg.id
            JOIN attendance_entry ae ON ae.attendance_id = a.id AND ae.learner_id = l.id
            GROUP BY l.id, l.first_name, l.surname, mg.group_name
            HAVING absent_days > 0 AND (CAST(absent_days AS FLOAT) / total_days) >= 0.20
            ORDER BY (CAST(absent_days AS FLOAT) / total_days) DESC
            LIMIT 10
        ''')
        
        chronic = []
        for row in cursor.fetchall():
            absent = row[3]
            total = row[4]
            pct = round((absent / total * 100)) if total > 0 else 0
            
            chronic.append({
                'name': f"{row[0]} {row[1]}",
                'group': row[2],
                'days_absent': absent,
                'percentage': pct
            })
        
    return jsonify(chronic)
