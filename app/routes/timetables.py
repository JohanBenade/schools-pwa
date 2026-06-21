"""
Timetables routes - look up any staff member's or learner's day.
"""

from datetime import date
from flask import Blueprint, render_template, session, redirect, request
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles
from app.services.substitute_engine import get_cycle_day

timetables_bp = Blueprint('timetables', __name__, url_prefix='/timetables')

TENANT_ID = "MARAGON"


def _resolve_day(cursor, target_date):
    """Return (cycle_day, day_type, bell_schedule, day_name) for a date.
    Mirrors the canonical resolution used in duty.my_day."""
    target_date_str = target_date.isoformat()
    weekday = target_date.weekday()
    cursor.execute("""
        SELECT cycle_day, day_type, bell_schedule, day_name
        FROM school_calendar
        WHERE tenant_id = ? AND date = ?
    """, (TENANT_ID, target_date_str))
    cal_row = cursor.fetchone()
    if cal_row:
        return (cal_row['cycle_day'], cal_row['day_type'],
                cal_row['bell_schedule'], cal_row['day_name'])
    cycle_day = get_cycle_day()
    day_type = 'academic' if weekday < 5 else 'weekend'
    if weekday in [0, 2]:
        bell_schedule = 'type_a'
    elif weekday in [1, 3]:
        bell_schedule = 'type_b'
    elif weekday == 4:
        bell_schedule = 'type_c'
    else:
        bell_schedule = 'none'
    day_name = f"D{cycle_day}" if cycle_day else None
    return (cycle_day, day_type, bell_schedule, day_name)


@timetables_bp.route('/')
def index():
    """Timetable finder - any app user can look up any staff member's or learner's day."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.id, s.display_name, us.role,
                   CASE 
                       WHEN s.display_name LIKE 'Mr %' THEN SUBSTR(s.display_name, 4)
                       WHEN s.display_name LIKE 'Ms %' THEN SUBSTR(s.display_name, 4)
                       WHEN s.display_name LIKE 'Mrs %' THEN SUBSTR(s.display_name, 5)
                       ELSE s.display_name
                   END as sort_name
            FROM staff s
            LEFT JOIN user_session us ON s.id = us.staff_id AND us.tenant_id = s.tenant_id
            WHERE s.tenant_id = ? AND s.is_active = 1
            ORDER BY sort_name
        """, (TENANT_ID,))
        teachers = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT l.id, l.first_name, l.surname, mg.group_name
            FROM learner l
            LEFT JOIN mentor_group mg ON l.mentor_group_id = mg.id AND mg.tenant_id = l.tenant_id
            WHERE l.tenant_id = ? AND l.is_active = 1
            ORDER BY l.first_name, l.surname
        """, (TENANT_ID,))
        learners = [dict(row) for row in cursor.fetchall()]

    _from = request.args.get('from')
    if _from == 'ops':
        _back_url, _back_label = "/tools/", "Operations"
    else:
        _back_url, _back_label = "/", "Home"
    nav_header = get_nav_header("Timetables", _back_url, _back_label)
    nav_styles = get_nav_styles()

    return render_template('timetables/index.html',
                          teachers=teachers,
                          learners=learners,
                          nav_header=nav_header,
                          nav_styles=nav_styles)


@timetables_bp.route('/learner/<learner_id>')
def learner_timetable(learner_id):
    """A single learner's period-by-period schedule for today."""
    target_date = date.today()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT l.id, l.first_name, l.surname, mg.group_name, g.grade_name
            FROM learner l
            LEFT JOIN mentor_group mg ON l.mentor_group_id = mg.id AND mg.tenant_id = l.tenant_id
            LEFT JOIN grade g ON l.grade_id = g.id AND g.tenant_id = l.tenant_id
            WHERE l.id = ? AND l.tenant_id = ? AND l.is_active = 1
        """, (learner_id, TENANT_ID))
        learner = cursor.fetchone()
        if not learner:
            return redirect('/timetables/')
        learner = dict(learner)

        cycle_day, day_type, bell_schedule, day_name = _resolve_day(cursor, target_date)

        slots = []
        if cycle_day:
            cursor.execute("""
                SELECT t.subject, t.class_name,
                       p.period_number, p.period_name, p.start_time, p.end_time, p.sort_order,
                       v.venue_code, s.display_name AS teacher_name
                FROM timetable_slot t
                JOIN period p ON t.period_id = p.id
                LEFT JOIN venue v ON t.venue_id = v.id
                LEFT JOIN staff s ON t.staff_id = s.id
                JOIN learner_subject ls
                     ON ls.subject = t.subject AND ls.class_name = t.class_name
                     AND ls.tenant_id = t.tenant_id AND ls.is_active = 1
                WHERE ls.learner_id = ? AND t.cycle_day = ? AND t.tenant_id = ?
                ORDER BY p.sort_order
            """, (learner_id, cycle_day, TENANT_ID))
            slots = [dict(row) for row in cursor.fetchall()]

    display_date = target_date.strftime('%A, %d %B %Y')
    nav_header = get_nav_header("Learner Timetable", "/timetables/", "Find")
    nav_styles = get_nav_styles()

    return render_template('timetables/learner.html',
                          learner=learner,
                          slots=slots,
                          cycle_day=cycle_day,
                          day_name=day_name,
                          day_type=day_type,
                          display_date=display_date,
                          nav_header=nav_header,
                          nav_styles=nav_styles)
