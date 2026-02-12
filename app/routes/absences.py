"""
Absences Module - Teacher and Learner absence tracking for leadership
"""
from flask import Blueprint, render_template, session
from app.services.db import get_connection
from datetime import datetime, date, timedelta

absences_bp = Blueprint('absences', __name__, url_prefix='/absences')

TENANT_ID = "MARAGON"


def get_last_attendance_date():
    """Get the most recent date with submitted attendance records."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(date) as last_date 
            FROM attendance 
            WHERE tenant_id = ? AND status = 'Submitted'
        """, (TENANT_ID,))
        row = cursor.fetchone()
        if row and row['last_date']:
            return row['last_date']
        return None


@absences_bp.route('/')
def index():
    """Absences home - choice between Teachers and Learners."""
    return render_template('absences/index.html')


@absences_bp.route('/learners')
def learners():
    """Learner absence list - sorted by consecutive days descending."""
    last_date = get_last_attendance_date()
    
    if not last_date:
        return render_template('absences/learners.html', 
                               learners=[], 
                               as_of_date=None,
                               total_absent=0)
    
    # Get all learners with consecutive absences
    # We need to calculate consecutive days from attendance_entry
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get learners marked absent on the last attendance date
        # and calculate their consecutive absence streak
        cursor.execute("""
            WITH latest_absences AS (
                SELECT DISTINCT ae.learner_id
                FROM attendance_entry ae
                JOIN attendance a ON ae.attendance_id = a.id
                WHERE a.tenant_id = ?
                  AND a.date = ?
                  AND a.status = 'Submitted'
                  AND ae.status = 'Absent'
            ),
            absence_dates AS (
                SELECT ae.learner_id, a.date
                FROM attendance_entry ae
                JOIN attendance a ON ae.attendance_id = a.id
                WHERE a.tenant_id = ?
                  AND a.status = 'Submitted'
                  AND ae.status = 'Absent'
                  AND ae.learner_id IN (SELECT learner_id FROM latest_absences)
                ORDER BY ae.learner_id, a.date DESC
            )
            SELECT 
                l.id,
                l.first_name,
                l.surname,
                mg.group_name as mentor_group,
                s.display_name as mentor_teacher,
                lat.consecutive_absent_days,
                lat.last_attendance_date
            FROM latest_absences la
            JOIN learner l ON la.learner_id = l.id
            LEFT JOIN mentor_group mg ON l.mentor_group_id = mg.id
            LEFT JOIN staff s ON mg.mentor_id = s.id
            LEFT JOIN learner_absent_tracking lat ON l.id = lat.learner_id
            WHERE l.is_active = 1
            ORDER BY l.first_name ASC
        """, (TENANT_ID, last_date, TENANT_ID))
        
        rows = cursor.fetchall()
        
        learners = []
        for row in rows:
            consecutive_days = row['consecutive_absent_days'] or 1
            
            # Calculate "absent since" date
            last_date_obj = datetime.strptime(last_date, '%Y-%m-%d').date()
            # Go back consecutive_days - 1 to get first absent date
            # (we need to account for weekends, but for now simple calc)
            absent_since = last_date_obj - timedelta(days=consecutive_days - 1)
            
            learners.append({
                'id': row['id'],
                'first_name': row['first_name'],
                'surname': row['surname'],
                'mentor_group': row['mentor_group'] or '-',
                'mentor_teacher': row['mentor_teacher'] or '-',
                'consecutive_days': consecutive_days,
                'absent_since': absent_since.strftime('%a %d %b')
            })
        
        # Format the as_of_date for display
        as_of_date_obj = datetime.strptime(last_date, '%Y-%m-%d').date()
        as_of_display = as_of_date_obj.strftime('%a %d %b')
        
        return render_template('absences/learners.html',
                               learners=learners,
                               as_of_date=as_of_display,
                               total_absent=len(learners))


@absences_bp.route('/teachers')
def teachers():
    """Teacher absence list with coverage status."""
    today = date.today()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get current/upcoming absences (today onwards, or open-ended)
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name, s.surname,
                   mg.group_name as mentor_class
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            LEFT JOIN mentor_group mg ON mg.mentor_id = s.id
            WHERE a.tenant_id = ?
              AND a.status NOT IN ('Resolved', 'Cancelled')
              AND (
                  COALESCE(a.end_date, a.absence_date) >= ?
                  OR a.is_open_ended = 1
              )
            ORDER BY s.display_name ASC
        """, (TENANT_ID, today.isoformat()))
        
        absences = []
        for row in cursor.fetchall():
            absence = dict(row)
            
            # Format dates for display
            start_date = datetime.strptime(absence['absence_date'], '%Y-%m-%d').date()
            absence['start_display'] = start_date.strftime('%a %d %b')
            
            if absence.get('end_date'):
                end_date = datetime.strptime(absence['end_date'], '%Y-%m-%d').date()
                absence['end_display'] = end_date.strftime('%a %d %b')
            else:
                absence['end_display'] = absence['start_display']
            
            absences.append(absence)
        
        return render_template('absences/teachers.html', absences=absences)
