"""
Attendance routes - Roll call functionality
"""

from flask import Blueprint, render_template, request, session, redirect, url_for
from datetime import date, datetime
from app.services.db import (
    get_mentor_groups_sqlite,
    get_mentor_group_by_id_sqlite,
    get_mentor_group_with_mentor_sqlite,
    get_learners_by_mentor_group_sqlite,
    mark_learner_sqlite,
    get_pending_marks_sqlite,
    get_pending_stats_sqlite,
    clear_pending_attendance_sqlite,
    create_attendance,
    create_attendance_entry,
    update_learner_absent_tracking,
    get_attendance_for_today,
    get_attendance_entries,
    update_attendance_entry,
    update_attendance_submitted
)

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')

TENANT_ID = "MARAGON"


@attendance_bp.route('/')
def index():
    groups = get_mentor_groups_sqlite(TENANT_ID)
    today_str = date.today().isoformat()
    
    for group in groups:
        existing = get_attendance_for_today(group['id'], today_str)
        group['submitted'] = existing is not None
        group['submitted_at'] = existing['submitted_at'] if existing else None
    
    today_date = date.today().strftime('%A, %d %B %Y')
    return render_template('attendance/select_group.html', 
                         groups=groups, 
                         today_date=today_date,
                         nav_header=True,
                         nav_title='Roll Call',
                         nav_back_url='/',
                         nav_back_label='Home')


@attendance_bp.route('/roll-call/<mentor_group_id>')
def roll_call(mentor_group_id):
    session['current_mentor_group_id'] = mentor_group_id
    
    group = get_mentor_group_with_mentor_sqlite(mentor_group_id)
    if not group:
        return redirect(url_for('attendance.index'))
    
    learners = get_learners_by_mentor_group_sqlite(mentor_group_id)
    today_str = date.today().isoformat()
    
    existing_attendance = get_attendance_for_today(mentor_group_id, today_str)
    already_submitted = existing_attendance is not None
    submitted_at = None
    
    if already_submitted:
        session['existing_attendance_id'] = existing_attendance['id']
        marks = get_attendance_entries(existing_attendance['id'])
        submitted_at = existing_attendance['submitted_at']
        try:
            dt = datetime.fromisoformat(submitted_at)
            submitted_at = dt.strftime('%H:%M')
        except:
            pass
    else:
        session.pop('existing_attendance_id', None)
        marks = get_pending_marks_sqlite(mentor_group_id)
    
    for learner in learners:
        learner['status'] = marks.get(learner['id'], 'Unmarked')
    
    stats = get_pending_stats_sqlite(mentor_group_id)
    
    # Pass individual variables that template expects
    group_name = group['group_name']
    mentor_name = group.get('mentor_name', 'No mentor assigned')
    
    return render_template('attendance/roll_call.html',
                         group=group,
                         group_name=group_name,
                         mentor_name=mentor_name,
                         learners=learners,
                         stats=stats,
                         already_submitted=already_submitted,
                         submitted_at=submitted_at,
                         nav_header=True,
                         nav_title=group_name,
                         nav_back_url='/attendance/',
                         nav_back_label='Groups')


@attendance_bp.route('/mark/<learner_id>', methods=['POST'])
def mark_learner(learner_id):
    """Mark a learner's attendance status"""
    status = request.form.get('status', 'Present')
    mentor_group_id = session.get('current_mentor_group_id')
    existing_attendance_id = session.get('existing_attendance_id')
    
    if existing_attendance_id:
        update_attendance_entry(existing_attendance_id, learner_id, status)
    elif mentor_group_id:
        mark_learner_sqlite(mentor_group_id, learner_id, status)
    
    return '', 204


@attendance_bp.route('/stats')
def get_stats():
    mentor_group_id = session.get('current_mentor_group_id')
    existing_attendance_id = session.get('existing_attendance_id')
    
    if existing_attendance_id:
        marks = get_attendance_entries(existing_attendance_id)
        learners = get_learners_by_mentor_group_sqlite(mentor_group_id)
        total_learners = len(learners)
        marked_learners = set(marks.keys())
        
        stats = {
            'present': sum(1 for s in marks.values() if s == 'Present'),
            'absent': sum(1 for s in marks.values() if s == 'Absent'),
            'late': sum(1 for s in marks.values() if s == 'Late'),
            'unmarked': total_learners - len([s for s in marks.values() if s in ('Present', 'Absent', 'Late')])
        }
    elif mentor_group_id:
        stats = get_pending_stats_sqlite(mentor_group_id)
    else:
        stats = {'present': 0, 'absent': 0, 'late': 0, 'unmarked': 0}
    
    return render_template('attendance/partials/stats.html', stats=stats)


@attendance_bp.route('/submit', methods=['POST'])
def submit_attendance_route():
    mentor_group_id = session.get('current_mentor_group_id')
    existing_attendance_id = session.get('existing_attendance_id')
    
    if not mentor_group_id:
        return redirect(url_for('attendance.index'))
    
    today = date.today().isoformat()
    
    if existing_attendance_id:
        update_attendance_submitted(existing_attendance_id)
        marks = get_attendance_entries(existing_attendance_id)
        attendance_id = existing_attendance_id
    else:
        marks = get_pending_marks_sqlite(mentor_group_id)
        
        if not marks:
            return redirect(url_for('attendance.roll_call', mentor_group_id=mentor_group_id))
        
        attendance_id = create_attendance(
            tenant_id=TENANT_ID,
            attendance_date=today,
            mentor_group_id=mentor_group_id,
            submitted_by_id=None,
            status='Submitted'
        )
        
        for learner_id, status in marks.items():
            create_attendance_entry(
                attendance_id=attendance_id,
                learner_id=learner_id,
                status=status
            )
        
        clear_pending_attendance_sqlite(mentor_group_id)
    
    for learner_id, status in marks.items():
        if status == 'Absent':
            update_learner_absent_tracking(learner_id, increment=True)
        elif status in ('Present', 'Late'):
            update_learner_absent_tracking(learner_id, increment=False)
    
    session.pop('current_mentor_group_id', None)
    session.pop('existing_attendance_id', None)
    
    group = get_mentor_group_by_id_sqlite(mentor_group_id)
    is_update = existing_attendance_id is not None
    
    return render_template('attendance/success.html', 
                          group_name=group['group_name'] if group else 'Unknown',
                          count=len(marks),
                          is_update=is_update,
                          nav_header=True,
                          nav_title='Submitted',
                          nav_back_url='/',
                          nav_back_label='Home')


@attendance_bp.route('/learners')
def get_learners():
    """Return learner list partial for HTMX polling"""
    mentor_group_id = session.get('current_mentor_group_id')
    existing_attendance_id = session.get('existing_attendance_id')
    
    if not mentor_group_id:
        return '', 204
    
    learners = get_learners_by_mentor_group_sqlite(mentor_group_id)
    
    if existing_attendance_id:
        marks = get_attendance_entries(existing_attendance_id)
    else:
        marks = get_pending_marks_sqlite(mentor_group_id)
    
    for learner in learners:
        learner['status'] = marks.get(learner['id'], 'Unmarked')
    
    return render_template('attendance/partials/learner_list.html', learners=learners)
