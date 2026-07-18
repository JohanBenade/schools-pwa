"""
Absences Module - Teacher and Learner absence tracking for leadership
"""
from flask import Blueprint, render_template, session, redirect, request
from app.services.db import get_connection, get_whos_out_by_period, get_period_roster
from datetime import datetime, date, timedelta

absences_bp = Blueprint('absences', __name__, url_prefix='/absences')

TENANT_ID = "MARAGON"

BACK_REGISTRY = {
    "ops":        ("/tools/",     "Operations"),
    "my-day":     ("/duty/my-day", "My Day"),
    "dash":       ("/dashboard/", "Dashboard"),
    "staff":      ("/",           "Home"),
    "office":     ("/",           "Home"),
    "activities": ("/",           "Home"),
    "leadership": ("/",           "Home"),
}
ROLE_DEFAULT_FROM = {
    "principal":"ops","deputy":"ops","management":"ops","admin":"ops",
    "office":"office","activities":"activities","sport_coordinator":"activities",
    "teacher":"staff","grade_head":"staff",
}
def resolve_back():
    token = request.args.get("from", "")
    if token not in BACK_REGISTRY:
        token = ROLE_DEFAULT_FROM.get(session.get("role",""), "staff")
    url, label = BACK_REGISTRY[token]
    return token, url, label


def resolve_sub_back():
    token = request.args.get("from", "")
    if token == "whosout":
        return "/absences/?from=" + request.args.get("origin", ""), "Who's Out"
    if token in BACK_REGISTRY:
        url, label = BACK_REGISTRY[token]
        return url, label
    return "/absences/", "Who's Out"


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


def get_school_day_info(date_str):
    """(is_school_day, day_name) from school_calendar for this tenant.
    Missing row = treated as a school day (fail-open, matches dashboard #143)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_school_day, day_name FROM school_calendar WHERE tenant_id = ? AND date = ?",
            (TENANT_ID, date_str)
        )
        row = cursor.fetchone()
        if row is None:
            return True, None
        return bool(row['is_school_day']), row['day_name']


@absences_bp.route('/')
def index():
    """Absences home - choice between Teachers and Learners."""
    from_token, back_url, back_label = resolve_back()
    return render_template('absences/index.html',
                           from_token=from_token,
                           back_url=back_url,
                           back_label=back_label)


@absences_bp.route('/learners')
def learners():
    """Learner absence list - sorted by consecutive days descending."""
    back_url, back_label = resolve_sub_back()
    is_school_today, _ = get_school_day_info(date.today().isoformat())
    last_date = get_last_attendance_date()
    
    if not last_date:
        return render_template('absences/learners.html', 
                               learners=[], 
                               as_of_date=None,
                               total_absent=0,
                               back_url=back_url, back_label=back_label)
    
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
            ORDER BY COALESCE(lat.consecutive_absent_days, 1) DESC, l.first_name ASC, l.surname ASC
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
                               total_absent=len(learners),
                               no_school_today=not is_school_today,
                               back_url=back_url, back_label=back_label)


@absences_bp.route('/teachers')
def teachers():
    """Teacher absence list with coverage status."""
    back_url, back_label = resolve_sub_back()
    today = date.today()
    is_school, day_context = get_school_day_info(today.isoformat())
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get current/upcoming absences (today onwards, or open-ended)
        cursor.execute("""
            SELECT a.*, s.display_name as teacher_name, s.first_name, s.surname,
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
            ORDER BY s.first_name ASC, s.surname ASC
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
        
        return render_template('absences/teachers.html', absences=absences,
                               no_school_day=not is_school,
                               day_context=day_context,
                               back_url=back_url, back_label=back_label)


@absences_bp.route('/my-periods')
def my_periods():
    """Per-teacher view: absent learners in the logged-in teacher's periods today, grouped by period."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')
    back_url, back_label = resolve_sub_back()

    today_str = date.today().isoformat()
    today_display = date.today().strftime('%a %d %b')

    cycle_day = None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT cycle_day FROM school_calendar WHERE tenant_id = ? AND date = ?",
            (TENANT_ID, today_str)
        )
        row = cursor.fetchone()
        if row and row['cycle_day'] is not None:
            cycle_day = row['cycle_day']

    if cycle_day is None:
        return render_template('absences/my_periods.html',
                               periods=[],
                               today_display=today_display,
                               total_absent=0,
                               no_school_day=True,
                               back_url=back_url, back_label=back_label)

    periods = get_whos_out_by_period(staff_id, today_str, cycle_day, TENANT_ID)
    total_absent = sum(p['absent_count'] for p in periods)

    return render_template('absences/my_periods.html',
                           periods=periods,
                           today_display=today_display,
                           total_absent=total_absent,
                           no_school_day=False,
                           back_url=back_url, back_label=back_label)


@absences_bp.route('/class-register')
def class_register():
    """Full roster for one period's class+subject: who's in, who's out.

    Read-only. Exceptions-first; full in-class list collapsed in the template.
    Reached from My Day (teaching/sub period tap). class_name + subject identify
    the roster, so it resolves the same set regardless of who views it (covers
    the substitute case automatically).
    """
    class_name = request.args.get('class', '').strip()
    subject = request.args.get('subject', '').strip()
    if not class_name or not subject:
        return redirect('/duty/my-day')

    date_str = request.args.get('date', '').strip() or date.today().isoformat()
    try:
        display_date = date.fromisoformat(date_str).strftime('%a %d %b')
    except ValueError:
        date_str = date.today().isoformat()
        display_date = date.today().strftime('%a %d %b')

    period_label = request.args.get('period', '').strip()
    period_time = request.args.get('time', '').strip()
    back_url, back_label = resolve_sub_back()

    roster = get_period_roster(class_name, subject, date_str, TENANT_ID)

    # Split exceptions (not Present) from the in-class (Present) list.
    exceptions = [lr for lr in roster['learners'] if lr['status'] != 'Present']
    in_class = [lr for lr in roster['learners'] if lr['status'] == 'Present']

    return render_template('absences/class_register.html',
                           class_name=class_name,
                           subject=subject,
                           period_label=period_label,
                           period_time=period_time,
                           display_date=display_date,
                           total=roster['total'],
                           present_count=roster['present_count'],
                           exception_count=roster['exception_count'],
                           exceptions=exceptions,
                           in_class=in_class,
                           back_url=back_url, back_label=back_label)
